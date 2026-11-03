"""국가동물보호정보시스템 구조동물 조회 서비스(공공데이터포털) 클라이언트.

API 문서: 공공데이터포털 > 농림축산식품부 농림축산검역본부_국가동물보호정보시스템 구조동물 조회 서비스
"""

from __future__ import annotations

import requests

BASE_URL = "https://apis.data.go.kr/1543061/abandonmentPublicService_v2"
DOG_UPKIND = "417000"  # 축종 코드: 개

SUCCESS_CODES = {"00", "0", "0000"}


class ApiError(Exception):
    """API 호출이 실패했을 때 발생합니다."""


def _request(operation: str, params: dict, api_key: str, timeout: float = 10) -> dict:
    query = {"serviceKey": api_key, "_type": "json", **params}
    try:
        resp = requests.get(f"{BASE_URL}/{operation}", params=query, timeout=timeout)
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
    """유기견 목록을 조회합니다.

    Args:
        state: "notice"(공고중), "protect"(보호중), None(전체)
        upr_cd: 시도 코드
        bgnde, endde: 구조일 검색 범위 (YYYYMMDD)

    Returns:
        (유기견 목록, 전체 건수)
    """
    params = {"upkind": DOG_UPKIND, "pageNo": page, "numOfRows": rows}
    optional = {"state": state, "upr_cd": upr_cd, "bgnde": bgnde, "endde": endde}
    params.update({k: v for k, v in optional.items() if v})

    body = _request("abandonmentPublic_v2", params, api_key)
    return _items(body), int(body.get("totalCount") or 0)
