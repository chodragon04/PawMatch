# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""보호소 좌표 바로잡기: 공공데이터의 보호소 좌표가 주소와 맞지 않는 곳을 카카오 좌표로 고칩니다.

동물보호센터 정보 API의 위도·경도가 틀린 곳이 있습니다.
(예: 전북 장수군 보호소가 충북 청주 근처 좌표, 경남 거창군 보호소가 0,0)

- scripts/check_shelter_coords.py가 보호소 주소를 카카오 주소 검색으로 찾아 API 좌표와 비교하고,
  FIX_KM보다 많이 다른 곳만 pawmatch/shelter_coords.json에 저장합니다. (GitHub Actions에서 실행)
- 앱은 카카오를 부르지 않고 이 파일만 읽어서, 보호소 주소가 확인할 때와 같으면 고친 좌표를 씁니다.
  (보호소가 이사해 주소가 바뀌었으면 예전에 고친 좌표를 쓰지 않습니다)
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pawmatch.geo import _area_of, haversine_km

FIXES_FILE = Path(__file__).resolve().parent / "shelter_coords.json"
FIX_KM = 3.0  # API 좌표와 카카오 좌표가 이보다 멀면 고칩니다 (같은 건물도 서비스마다 조금씩 달라서 여유를 둠)
KOREA = (33.0, 38.7, 124.5, 132.0)  # 위도·경도 대략 범위 (제주~강원, 백령도~독도)

Geocode = Callable[[str], "tuple[float, float, str] | None"]
PlaceSearch = Callable[[str, str], "tuple[float, float, str] | None"]


def in_korea(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    south, north, west, east = KOREA
    return south <= lat <= north and west <= lng <= east


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def api_coords(shelter: dict) -> tuple[float, float] | None:
    """API가 준 좌표. 없거나 한국 밖(0,0 등)이면 None."""
    lat, lng = _to_float(shelter.get("lat")), _to_float(shelter.get("lng"))
    return (lat, lng) if in_korea(lat, lng) else None


def normalize_address(address: str | None) -> str:
    return re.sub(r"\s+", " ", address or "").strip()


# 도로명 주소의 '도로 이름 + 건물 번호'까지 (예: '... 감악산로 63-37', '... 운남동로3번길 9')
_ROAD_ADDRESS = re.compile(r"^(.+?[로길]\s+\d+(?:-\d+)?)(?:\s|\(|,|$)")


def clean_address(address: str | None) -> str:
    """카카오 주소 검색에 넣을 주소: 괄호와 그 뒤의 설명(시설 이름, '도로 옆' 등)을 뗍니다."""
    text = normalize_address(address)
    road = _ROAD_ADDRESS.match(text)
    if road:
        return road.group(1)
    return normalize_address(re.split(r"[(,]", text, maxsplit=1)[0])


def address_variants(address: str) -> list[str]:
    """검색해 볼 주소들: 정리한 주소, 그다음 통합·명칭 변경 전 시/도 이름으로 바꾼 주소 (카카오가 새 이름을 모를 때)."""
    from pawmatch.kakao import LEGACY_SIDO_NAMES

    cleaned = clean_address(address)
    first, _, rest = cleaned.partition(" ")
    return [cleaned, *(f"{old} {rest}" for old in LEGACY_SIDO_NAMES.get(first, ()))]


@dataclass
class CheckResult:
    reg_no: str
    name: str
    address: str
    api: tuple[float, float] | None
    kakao: tuple[float, float] | None
    found_as: str  # 카카오가 찾은 주소나 장소 ('' = 못 찾음)
    diff_km: float | None

    @property
    def needs_fix(self) -> bool:
        if self.kakao is None:
            return False
        return self.api is None or (self.diff_km is not None and self.diff_km > FIX_KM)


def check_shelter(shelter: dict, geocode: Geocode, search_place: PlaceSearch) -> CheckResult:
    """보호소 하나: 주소 → 카카오 좌표 (못 찾으면 '시/군/구 + 보호소 이름'으로 장소 검색) → API 좌표와 비교."""
    address = normalize_address(shelter.get("careAddr"))
    name = (shelter.get("careNm") or "").strip()
    found = None
    for query in address_variants(address) if address else []:
        found = geocode(query)
        if found:
            break
    if found is None and name:
        sigungu = _area_of(address)[1]
        found = search_place(f"{sigungu} {name}".strip(), sigungu)
    api = api_coords(shelter)
    kakao = (found[0], found[1]) if found else None
    diff = haversine_km(api, kakao) if api and kakao else None
    return CheckResult(
        str(shelter.get("careRegNo") or name), name, address, api, kakao, found[2] if found else "", diff
    )


def fixes_payload(results: list[CheckResult], checked_at: str) -> dict:
    """shelter_coords.json에 저장할 내용: 고칠 보호소만."""
    fixes = {
        r.reg_no: {
            "name": r.name,
            "address": r.address,
            "lat": round(r.kakao[0], 6),
            "lng": round(r.kakao[1], 6),
            "api": [round(r.api[0], 6), round(r.api[1], 6)] if r.api else None,
            "diff_km": round(r.diff_km, 1) if r.diff_km is not None else None,
            "found_as": r.found_as,
        }
        for r in results
        if r.needs_fix and r.kakao
    }
    return {"checked_at": checked_at, "fix_km": FIX_KM, "fixes": dict(sorted(fixes.items()))}


@lru_cache(maxsize=1)
def load_fixes(path: Path = FIXES_FILE) -> dict[str, dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("fixes", {})
    except (OSError, ValueError, AttributeError):
        return {}


def shelter_coords(shelter: dict, fixes: dict[str, dict] | None = None) -> tuple[float, float] | None:
    """앱에서 쓸 보호소 좌표: 고친 좌표(주소가 확인할 때와 같을 때만) → API 좌표(한국 안일 때만)."""
    fixes = load_fixes() if fixes is None else fixes
    fix = fixes.get(str(shelter.get("careRegNo") or ""))
    if fix and normalize_address(shelter.get("careAddr")) == fix.get("address"):
        return float(fix["lat"]), float(fix["lng"])
    return api_coords(shelter)
