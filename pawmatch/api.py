"""국가동물보호정보시스템 공공데이터포털 API 클라이언트.

- 구조동물 조회 서비스: 보호소에 있는 유기동물 목록
- 동물보호센터 정보 조회 서비스: 보호소 주소, 좌표, 연락처 등

출처: 공공데이터포털(data.go.kr), 농림축산식품부 농림축산검역본부
"""

from __future__ import annotations

import requests

BASE_URL = "https://apis.data.go.kr/1543061/abandonmentPublicService_v2"
SHELTER_BASE_URL = "https://apis.data.go.kr/1543061/animalShelterSrvc_v2"

DOG_UPKIND = "417000"  # 축종 코드: 개
MAX_ROWS = 1000  # 한 번에 요청할 최대 건수
MAX_PAGES = 20  # 무한 반복 방지용 상한

SUCCESS_CODES = {"00", "0", "0000"}


class ApiError(Exception):
    """API 호출이 실패했을 때 발생합니다."""


def _request(url: str, params: dict, api_key: str, timeout: float = 15) -> dict:
    query = {"serviceKey": api_key, "_type": "json", **params}
    try:
        resp = requests.get(url, params=query, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"API 서버에 연결하지 못했습니다: {exc}") from exc

    if resp.status_code != 200:
        raise ApiError(f"API 서버 응답 오류 (HTTP {resp.status_code}): {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError:
        # 인증키 오류 등은 JSON이 아니라 XML로 내려옵니다.
        raise ApiError(f"API가 예상하지 못한 응답을 보냈습니다: {resp.text[:300]}") from None

    header = data.get("response", {}).get("header", {})
    code = str(header.get("resultCode", ""))
    if code not in SUCCESS_CODES:
        raise ApiError(f"API 오류 ({code}): {header.get('resultMsg', '알 수 없는 오류')}")

    return data["response"].get("body", {})


def _items(body: dict) -> list[dict]:
    """응답 body에서 항목 리스트를 꺼냅니다. (결과가 0개/1개일 때 형태가 달라지는 것을 처리)"""
    items = body.get("items") or {}
    if not isinstance(items, dict):
        return []
    item = items.get("item") or []
    return [item] if isinstance(item, dict) else list(item)


def _fetch_all_pages(url: str, params: dict, api_key: str) -> list[dict]:
    """여러 페이지에 걸친 결과를 모두 가져옵니다."""
    collected: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        body = _request(url, {**params, "pageNo": page, "numOfRows": MAX_ROWS}, api_key)
        items = _items(body)
        collected.extend(items)
        total = int(body.get("totalCount") or 0)
        if not items or len(collected) >= total:
            break
    return collected


def dedupe_by_id(dogs: list[dict]) -> list[dict]:
    """구조번호(desertionNo)가 같은 항목은 처음 것만 남깁니다."""
    seen: set[str] = set()
    unique = []
    for dog in dogs:
        key = dog.get("desertionNo")
        if key:
            if key in seen:
                continue
            seen.add(key)
        unique.append(dog)
    return unique


def _dog_params(state, upr_cd, bgnde, endde) -> dict:
    params = {"upkind": DOG_UPKIND}
    optional = {"state": state, "upr_cd": upr_cd, "bgnde": bgnde, "endde": endde}
    params.update({k: v for k, v in optional.items() if v})
    return params


def fetch_abandoned_dogs(
    api_key: str,
    *,
    state: str | None = "protect",
    page: int = 1,
    rows: int = 20,
    upr_cd: str | None = None,
    bgnde: str | None = None,
    endde: str | None = None,
) -> tuple[list[dict], int]:
    """유기견 목록 한 페이지를 조회합니다.

    Args:
        state: "notice"(공고중), "protect"(보호중), None(전체)
        upr_cd: 시도 코드
        bgnde, endde: 구조일 검색 범위 (YYYYMMDD)

    Returns:
        (유기견 목록, 전체 건수)
    """
    params = {**_dog_params(state, upr_cd, bgnde, endde), "pageNo": page, "numOfRows": rows}
    body = _request(f"{BASE_URL}/abandonmentPublic_v2", params, api_key)
    return dedupe_by_id(_items(body)), int(body.get("totalCount") or 0)


def fetch_all_dogs(api_key: str, states: tuple[str, ...] = ("notice", "protect")) -> list[dict]:
    """공고 중 + 보호 중인 유기견을 모두 가져옵니다."""
    dogs: list[dict] = []
    for state in states:
        dogs.extend(
            _fetch_all_pages(
                f"{BASE_URL}/abandonmentPublic_v2", _dog_params(state, None, None, None), api_key
            )
        )
    return dedupe_by_id(dogs)


def fetch_shelters(api_key: str) -> list[dict]:
    """전국 동물보호센터 목록(주소, 위도/경도 포함)을 가져옵니다."""
    return _fetch_all_pages(f"{SHELTER_BASE_URL}/shelterInfo_v2", {}, api_key)
