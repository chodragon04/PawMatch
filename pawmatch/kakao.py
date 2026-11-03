"""카카오 로컬 API로 시/군/구의 위치(위도, 경도)를 찾습니다.

시/군/구를 고르면 그 지역 중심 좌표를 기준으로 가까운 보호소를 찾기 위해 씁니다.
API 키(KAKAO_REST_API_KEY)가 없거나 찾지 못하면 None을 돌려주고, 화면에서는 시/도청 위치로 대신합니다.

출처: 카카오 로컬 API 주소 검색 (https://developers.kakao.com/docs/latest/ko/local/dev-guide)
"""

from __future__ import annotations

import requests

ADDRESS_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/address.json"

# 통합·명칭 변경 전 이름. 카카오 주소 데이터가 새 이름을 모를 때 대신 검색합니다.
LEGACY_SIDO_NAMES: dict[str, tuple[str, ...]] = {
    "전남광주통합특별시": ("광주광역시", "전라남도"),
    "강원특별자치도": ("강원도",),
    "전북특별자치도": ("전라북도",),
}


def region_queries(sido: str, sigungu: str) -> list[str]:
    """검색해 볼 주소 문자열 목록 (앞에서부터 시도)."""
    names = (sido, *LEGACY_SIDO_NAMES.get(sido, ()))
    return [f"{name} {sigungu}".strip() for name in names]


def _first_match(documents: list[dict], sigungu: str) -> tuple[float, float] | None:
    for doc in documents:
        if sigungu and sigungu not in (doc.get("address_name") or ""):
            continue
        try:
            return float(doc["y"]), float(doc["x"])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def geocode_region(sido: str, sigungu: str, api_key: str, timeout: float = 5) -> tuple[float, float] | None:
    """'경기도', '수원시' → (위도, 경도). 찾지 못하면 None."""
    headers = {"Authorization": f"KakaoAK {api_key}"}
    for query in region_queries(sido, sigungu):
        try:
            resp = requests.get(
                ADDRESS_SEARCH_URL, params={"query": query, "analyze_type": "exact"}, headers=headers, timeout=timeout
            )
        except requests.RequestException:
            return None
        if resp.status_code != 200:  # 키 오류(401) 등은 다른 검색어로 바꿔도 소용없습니다
            return None
        try:
            documents = resp.json().get("documents") or []
        except ValueError:
            return None
        found = _first_match(documents, sigungu)
        if found:
            return found
    return None
