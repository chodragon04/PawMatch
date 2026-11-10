# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""위치/거리 계산: 사용자 위치에서 가까운 보호소 순으로 정렬합니다."""

from __future__ import annotations

import math
import re

# 위치 권한을 허용하지 않은 경우 시/도를 고르면 시청/도청 위치를 기준으로 거리를 계산합니다.
# (좌표는 직접 입력한 대략적인 값입니다)
# 시/도 이름은 구조동물 조회 API의 시/도 목록(16곳)과 같습니다.
REGION_CENTERS: dict[str, tuple[float, float]] = {
    "서울특별시": (37.5665, 126.9780),
    "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014),
    "인천광역시": (37.4563, 126.7052),
    "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114),
    "세종특별자치시": (36.4800, 127.2890),
    "경기도": (37.2752, 127.0095),
    "강원특별자치도": (37.8813, 127.7298),
    "충청북도": (36.6357, 127.4917),
    "충청남도": (36.6588, 126.6728),
    "전북특별자치도": (35.8203, 127.1088),
    "전남광주통합특별시": (35.1595, 126.8526),  # 통합 전 광주광역시청 위치
    "경상북도": (36.5760, 128.5056),
    "경상남도": (35.2383, 128.6924),
    "제주특별자치도": (33.4996, 126.5312),
}

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """두 위경도 좌표 사이의 거리(km). 하버사인 공식: https://en.wikipedia.org/wiki/Haversine_formula"""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def _to_float(value) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) and f != 0 else None


def _normalize_name(name: str | None) -> str:
    return re.sub(r"[\s()（）]", "", name or "")


class ShelterLocator:
    """유기견 정보에서 보호소 좌표를 찾습니다. (보호소 번호 → 보호소 이름 순으로 매칭)"""

    def __init__(self, shelters: list[dict]):
        self.by_reg_no: dict[str, tuple[float, float]] = {}
        self.by_name: dict[str, tuple[float, float]] = {}
        self.records_by_reg_no: dict[str, dict] = {}
        self.records_by_name: dict[str, dict] = {}
        for s in shelters:
            if s.get("careRegNo"):
                self.records_by_reg_no.setdefault(str(s["careRegNo"]), s)
            if s.get("careNm"):
                self.records_by_name.setdefault(_normalize_name(s["careNm"]), s)
            lat, lng = _to_float(s.get("lat")), _to_float(s.get("lng"))
            if lat is None or lng is None:
                continue
            if s.get("careRegNo"):
                self.by_reg_no[str(s["careRegNo"])] = (lat, lng)
            if s.get("careNm"):
                self.by_name[_normalize_name(s["careNm"])] = (lat, lng)

    def locate(self, dog: dict) -> tuple[float, float] | None:
        reg_no = dog.get("careRegNo")
        if reg_no and str(reg_no) in self.by_reg_no:
            return self.by_reg_no[str(reg_no)]
        return self.by_name.get(_normalize_name(dog.get("careNm")))

    def shelter_info(self, dog: dict) -> dict | None:
        """유기견이 있는 보호소의 정보(운영 시간 등). 보호소 번호 → 이름 순으로 찾습니다."""
        reg_no = dog.get("careRegNo")
        if reg_no and str(reg_no) in self.records_by_reg_no:
            return self.records_by_reg_no[str(reg_no)]
        return self.records_by_name.get(_normalize_name(dog.get("careNm")))


def sort_by_distance(
    dogs: list[dict], locator: ShelterLocator, origin: tuple[float, float]
) -> list[tuple[dict, float | None]]:
    """가까운 순으로 정렬한 (유기견, 거리km) 목록. 좌표를 못 찾은 아이는 맨 뒤로 갑니다."""
    with_distance = []
    for dog in dogs:
        pos = locator.locate(dog)
        with_distance.append((dog, haversine_km(origin, pos) if pos else None))
    return sorted(with_distance, key=lambda x: (x[1] is None, x[1] or 0.0))


# 보호소 주소에 남아 있는 옛 이름·줄임말 → 지금 시/도 이름 (REGION_CENTERS의 키)
SIDO_ALIASES = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시", "대전": "대전광역시",
    "울산": "울산광역시", "세종": "세종특별자치시", "세종시": "세종특별자치시", "경기": "경기도",
    "강원": "강원특별자치도", "강원도": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도",
    "광주": "전남광주통합특별시", "광주광역시": "전남광주통합특별시", "전남": "전남광주통합특별시",
    "전라남도": "전남광주통합특별시",
}  # fmt: skip


# 2026년 인천 행정체제 개편 전 주소: 동 이름으로 새 구를 정합니다.
# (중구 영종도 지역 → 영종구, 나머지 중구·동구 → 제물포구 / 서구 검단 지역 → 검단구, 나머지 서구 → 서해구)
# 도로명 주소 끝 괄호 안의 동 이름('(운남동)')을 먼저 보고, 괄호에 동 이름이 없으면 주소 전체에서 찾습니다.
# (도로 이름에 다른 지역 이름이 들어 있어도 실제 동으로 판단하기 위해서)
# 영종도 안의 도로는 '공항로', '공항동로'처럼 이름에 '공항'이 들어가서 괄호가 없어도 영종구로 봅니다.
_INCHEON_LEGACY = {
    "중구": (("운서", "운남", "운북", "중산", "영종", "용유", "을왕", "남북동", "덕교", "무의", "공항"), "영종구", "제물포구"),
    "동구": ((), "", "제물포구"),
    "서구": (("검단", "마전", "당하", "원당", "불로", "대곡", "오류", "왕길", "금곡", "아라"), "검단구", "서해구"),
}  # fmt: skip


def _current_sigungu(sido: str, sigungu: str, address: str) -> str:
    if sido == "인천광역시" and sigungu in _INCHEON_LEGACY:
        keywords, matched, default = _INCHEON_LEGACY[sigungu]
        inside = re.search(r"\(([^)]*)\)", address)  # 도로명 주소 끝의 '(운남동)', '(경동, ...)'
        dongs = re.findall(r"[가-힣0-9]+동", inside.group(1)) if inside else []
        where = " ".join(dongs) if dongs else address  # 괄호에 동 이름이 없으면('(2층)') 주소 전체에서 찾기
        return matched if any(k in where for k in keywords) else default
    return sigungu


def _area_of(address: str | None) -> tuple[str, str]:
    """주소의 (시/도, 시/군/구). 옛 이름은 지금 이름으로 바꿉니다. 세종은 시/군/구가 없어 ''."""
    tokens = (address or "").split()
    if not tokens:
        return "", ""
    sido = SIDO_ALIASES.get(tokens[0], tokens[0])
    if sido == "세종특별자치시" or len(tokens) < 2:
        return sido, ""
    return sido, _current_sigungu(sido, tokens[1], address or "")


def address_in_area(address: str | None, sido: str, sigungu: str | None = None) -> bool:
    """주소가 고른 시/도(와 시/군/구) 안인지. 예: '인천광역시 연수구 ...' → ('인천광역시', '연수구')

    시/군/구는 주소의 두 번째 낱말과 비교합니다. ('경기도 수원시 영통구 ...'는 수원시)
    """
    tokens = (address or "").split()
    if not tokens or SIDO_ALIASES.get(tokens[0], tokens[0]) != sido:
        return False
    if not sigungu:
        return True
    if sido == "세종특별자치시":
        return True
    return len(tokens) > 1 and _current_sigungu(sido, tokens[1], address or "") == sigungu


def group_by_shelter(
    ranked: list[tuple[dict, float | None]], area: tuple[str, str | None] | None = None
) -> list[dict]:
    """거리순 목록을 보호소별로 묶습니다. 가까운 보호소가 먼저 오고, 좌표를 모르는 아이는 제외합니다.

    area(시/도, 시/군/구 또는 None)를 주면 주소가 그 지역 안인 보호소를 먼저(가까운 순),
    그다음 나머지 보호소를 가까운 순으로 둡니다. 지역 안 보호소는 좌표를 몰라도 포함합니다.

    Returns:
        [{"name", "distance_km", "address", "tel", "in_area", "dogs": [...]}, ...]
    """
    groups: dict[tuple[str, str, str], dict] = {}
    for dog, distance in ranked:
        inside = area is not None and address_in_area(dog.get("careAddr"), *area)
        if distance is None and not inside:
            continue
        # 이름이 같은 다른 지역 보호소(예: 청주·여수의 '반려동물보호센터')가 합쳐지지 않게 지역도 함께 봅니다.
        name = _normalize_name(dog.get("careNm"))
        key = (name, *_area_of(dog.get("careAddr"))) if name else ("", str(dog.get("careRegNo")), "")
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                "name": dog.get("careNm") or "보호소",
                "distance_km": distance,
                "address": dog.get("careAddr") or "",
                "tel": dog.get("careTel") or "",
                "in_area": False,
                "dogs": [],
            }
        group["in_area"] = group["in_area"] or inside
        group["dogs"].append(dog)

    return sorted(
        groups.values(), key=lambda g: (not g["in_area"], g["distance_km"] is None, g["distance_km"] or 0.0)
    )
