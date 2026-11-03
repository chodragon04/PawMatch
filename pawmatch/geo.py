"""위치/거리 계산: 사용자 위치에서 가까운 보호소 순으로 정렬합니다."""

from __future__ import annotations

import math
import re

# 위치 권한을 허용하지 않은 경우 시/도를 고르면 시청/도청 위치를 기준으로 거리를 계산합니다.
REGION_CENTERS: dict[str, tuple[float, float]] = {
    "서울특별시": (37.5665, 126.9780),
    "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014),
    "인천광역시": (37.4563, 126.7052),
    "광주광역시": (35.1595, 126.8526),
    "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114),
    "세종특별자치시": (36.4800, 127.2890),
    "경기도": (37.2752, 127.0095),
    "강원특별자치도": (37.8813, 127.7298),
    "충청북도": (36.6357, 127.4917),
    "충청남도": (36.6588, 126.6728),
    "전북특별자치도": (35.8203, 127.1088),
    "전라남도": (34.8161, 126.4629),
    "경상북도": (36.5760, 128.5056),
    "경상남도": (35.2383, 128.6924),
    "제주특별자치도": (33.4996, 126.5312),
}

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """두 위경도 좌표 사이의 거리(km)."""
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
        for s in shelters:
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


def sort_by_distance(
    dogs: list[dict], locator: ShelterLocator, origin: tuple[float, float]
) -> list[tuple[dict, float | None]]:
    """가까운 순으로 정렬한 (유기견, 거리km) 목록. 좌표를 못 찾은 아이는 맨 뒤로 갑니다."""
    with_distance = []
    for dog in dogs:
        pos = locator.locate(dog)
        with_distance.append((dog, haversine_km(origin, pos) if pos else None))
    return sorted(with_distance, key=lambda x: (x[1] is None, x[1] or 0.0))


def group_by_shelter(ranked: list[tuple[dict, float | None]]) -> list[dict]:
    """거리순 목록을 보호소별로 묶습니다. 가까운 보호소가 먼저 오고, 좌표를 모르는 아이는 제외합니다.

    Returns:
        [{"name", "distance_km", "address", "tel", "dogs": [...]}, ...]
    """
    groups: dict[str, dict] = {}
    for dog, distance in ranked:
        if distance is None:
            continue
        key = _normalize_name(dog.get("careNm")) or str(dog.get("careRegNo"))
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                "name": dog.get("careNm") or "보호소",
                "distance_km": distance,
                "address": dog.get("careAddr") or "",
                "tel": dog.get("careTel") or "",
                "dogs": [],
            }
        group["dogs"].append(dog)
    return sorted(groups.values(), key=lambda g: g["distance_km"])
