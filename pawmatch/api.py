# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""국가동물보호정보시스템 공공데이터포털 API 클라이언트.

- 구조동물 조회 서비스: 보호소에 있는 유기동물 목록
- 동물보호센터 정보 조회 서비스: 보호소 주소, 좌표, 연락처 등

출처: 공공데이터포털(data.go.kr), 농림축산식품부 농림축산검역본부
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

import requests

T = TypeVar("T")
R = TypeVar("R")

BASE_URL = "https://apis.data.go.kr/1543061/abandonmentPublicService_v2"
SHELTER_BASE_URL = "https://apis.data.go.kr/1543061/animalShelterSrvc_v2"

DOG_UPKIND = "417000"  # 축종 코드: 개
MAX_ROWS = 1000  # 한 번에 요청할 최대 건수
MAX_PAGES = 20  # 무한 반복 방지용 상한

SUCCESS_CODES = {"00", "0", "0000"}

# 서버 응답이 요청 크기와 상관없이 한 번에 2~9초 걸려서, 페이지를 동시에 요청합니다.
MAX_WORKERS = 4  # 동시에 보낼 최대 요청 수 (서버에 부담을 주지 않도록 작게 유지)
RETRIES = 2  # 연결 끊김·서버 오류(5xx) 때 다시 시도할 횟수
RETRY_BACKOFF = 1.0  # 재시도 간격(초), 시도할 때마다 두 배
DOG_PREFETCH_PAGES = 2  # 유기견은 상태별로 보통 1,000~2,000마리라 처음부터 2페이지씩 요청

# 연결을 재사용해 요청마다 TLS 연결을 새로 맺는 시간(약 0.6초)을 줄입니다.
_SESSION = requests.Session()
_SESSION.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=MAX_WORKERS * 2))


class ApiError(Exception):
    """API 호출이 실패했을 때 발생합니다."""


def _get_with_retry(url: str, query: dict, timeout: float) -> requests.Response:
    """연결 오류나 5xx 응답이면 잠깐 기다렸다가 다시 요청합니다."""
    for attempt in range(RETRIES + 1):
        last = attempt == RETRIES
        try:
            resp = _SESSION.get(url, params=query, timeout=timeout)
        except requests.RequestException as exc:
            if last:
                # 오류 문구(exc)에는 요청 주소 전체가 들어 있고, 그 안에 serviceKey가 있습니다.
                # 이 문구는 공개 Actions 로그와 사용자 화면에 나가므로 오류 종류만 남깁니다.
                raise ApiError(f"API 서버에 연결하지 못했습니다 ({type(exc).__name__})") from None
        else:
            if resp.status_code < 500 or last:
                return resp
        time.sleep(RETRY_BACKOFF * 2**attempt)
    raise AssertionError("unreachable")


def _request(url: str, params: dict, api_key: str, timeout: float = 30) -> dict:
    query = {"serviceKey": api_key, "_type": "json", **params}
    resp = _get_with_retry(url, query, timeout)

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


def _parallel_map(fn: Callable[[T], R], args: Iterable[T]) -> list[R]:
    """fn을 동시에 실행하고, 입력 순서대로 결과를 돌려줍니다."""
    args = list(args)
    if len(args) <= 1:
        return [fn(a) for a in args]
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(args))) as pool:
        return list(pool.map(fn, args))


def _fetch_all_pages(url: str, params: dict, api_key: str, prefetch: int = 1) -> list[dict]:
    """여러 페이지에 걸친 결과를 모두 가져옵니다.

    처음에 `prefetch`개 페이지를 동시에 요청하고, 1페이지의 전체 건수(totalCount)를 보고
    더 필요한 페이지가 있으면 나머지도 한꺼번에 동시에 요청합니다.
    """

    def fetch(page: int) -> dict:
        return _request(url, {**params, "pageNo": page, "numOfRows": MAX_ROWS}, api_key)

    first = _parallel_map(fetch, range(1, min(max(prefetch, 1), MAX_PAGES) + 1))
    pages = [_items(body) for body in first]

    total = int(first[0].get("totalCount") or 0)
    needed = min(math.ceil(total / MAX_ROWS), MAX_PAGES)
    # 보호소 API는 totalCount가 실제보다 크게 와서(861 vs 338), 덜 찬 페이지가 나오면 멈춥니다.
    if needed > len(pages) and all(len(items) == MAX_ROWS for items in pages):
        pages += [_items(body) for body in _parallel_map(fetch, range(len(pages) + 1, needed + 1))]

    return [item for items in pages for item in items]


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
    """공고 중 + 보호 중인 유기견을 모두 가져옵니다. (상태별로 동시에 요청)"""
    per_state = _parallel_map(
        lambda state: _fetch_all_pages(
            f"{BASE_URL}/abandonmentPublic_v2",
            _dog_params(state, None, None, None),
            api_key,
            prefetch=DOG_PREFETCH_PAGES,
        ),
        states,
    )
    return dedupe_by_id([dog for dogs in per_state for dog in dogs])


def fetch_shelters(api_key: str) -> list[dict]:
    """전국 동물보호센터 목록(주소, 위도/경도 포함)을 가져옵니다."""
    return _fetch_all_pages(f"{SHELTER_BASE_URL}/shelterInfo_v2", {}, api_key)
