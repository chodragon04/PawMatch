# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
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


# ---------------------------------------------------------------- 보호소 좌표 확인용 (scripts/check_shelter_coords.py)

KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoError(Exception):
    """카카오 API가 정상 응답을 주지 않았을 때 (키 오류, 사용량 초과 등)."""


def _get_documents(url: str, query: str, api_key: str, timeout: float) -> list[dict]:
    try:
        resp = requests.get(url, params={"query": query}, headers={"Authorization": f"KakaoAK {api_key}"}, timeout=timeout)
    except requests.RequestException as exc:
        raise KakaoError(f"카카오 API에 연결하지 못했습니다 ({type(exc).__name__})") from None
    if resp.status_code != 200:
        raise KakaoError(f"카카오 API 응답 오류 (HTTP {resp.status_code})")
    try:
        return resp.json().get("documents") or []
    except ValueError:
        raise KakaoError("카카오 API가 예상하지 못한 응답을 보냈습니다") from None


def geocode_address(address: str, api_key: str, timeout: float = 5) -> tuple[float, float, str] | None:
    """주소 → (위도, 경도, 카카오가 찾은 주소). 찾지 못하면 None."""
    for doc in _get_documents(ADDRESS_SEARCH_URL, address, api_key, timeout):
        try:
            return float(doc["y"]), float(doc["x"]), doc.get("address_name") or ""
        except (KeyError, TypeError, ValueError):
            continue
    return None


def search_place(query: str, must_contain: str, api_key: str, timeout: float = 5) -> tuple[float, float, str] | None:
    """장소 이름 검색 → (위도, 경도, 장소 주소). 주소에 must_contain(시/군/구)이 들어간 첫 결과만 씁니다."""
    for doc in _get_documents(KEYWORD_SEARCH_URL, query, api_key, timeout):
        address = doc.get("address_name") or doc.get("road_address_name") or ""
        if must_contain and must_contain not in address:
            continue
        try:
            return float(doc["y"]), float(doc["x"]), f"{doc.get('place_name', '')} ({address})"
        except (KeyError, TypeError, ValueError):
            continue
    return None
