# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""지역 목록(pawmatch.regions, scripts/build_regions.py)과 카카오 위치 찾기(pawmatch.kakao) 테스트."""

import importlib.util
from pathlib import Path

import pytest
import requests

from pawmatch import kakao
from pawmatch.geo import REGION_CENTERS
from pawmatch.regions import load_regions

_spec = importlib.util.spec_from_file_location(
    "build_regions", Path(__file__).resolve().parent.parent / "scripts" / "build_regions.py"
)
build_regions = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_regions)


def test_regions_cover_every_sido_with_a_center():
    regions = load_regions()
    assert set(regions) == set(REGION_CENTERS)
    assert len(regions["서울특별시"]) == 25 and len(regions["경기도"]) == 31
    assert "수원시" in regions["경기도"] and "권선구" not in regions["경기도"]  # 일반구 제외
    assert regions["세종특별자치시"] == ()


def test_clean_sigungu():
    names = ["강남구", "서울특별시", "가정보호", None, "강남구", "중구"]
    assert build_regions.clean_sigungu("서울특별시", names) == ["강남구", "중구"]
    assert build_regions.clean_sigungu("경기도", ["수원시", "권선구", "영통구"]) == ["수원시"]
    assert build_regions.clean_sigungu("충청남도", ["연기군", "천안시"]) == ["천안시"]
    # 광역시가 합쳐진 전남광주통합특별시의 구는 자치구라서 남깁니다
    assert build_regions.clean_sigungu("전남광주통합특별시", ["북구", "목포시"]) == ["목포시", "북구"]


def test_region_queries_try_legacy_names():
    assert kakao.region_queries("경기도", "수원시") == ["경기도 수원시"]
    assert kakao.region_queries("전남광주통합특별시", "북구") == [
        "전남광주통합특별시 북구", "광주광역시 북구", "전라남도 북구",
    ]  # fmt: skip


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


def doc(name, x, y):
    return {"address_name": name, "address_type": "REGION", "x": str(x), "y": str(y)}


@pytest.fixture
def fake_kakao(monkeypatch):
    calls = []

    def install(responses):
        def _get(url, params=None, headers=None, timeout=None):
            calls.append((params["query"], headers["Authorization"]))
            r = responses.get(params["query"], FakeResponse({"documents": []}))
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(kakao.requests, "get", _get)
        return calls

    return install


def test_geocode_region_returns_lat_lng(fake_kakao):
    calls = fake_kakao({"경기도 수원시": FakeResponse({"documents": [doc("경기 수원시", 127.0286, 37.2636)]})})
    assert kakao.geocode_region("경기도", "수원시", "KEY") == (37.2636, 127.0286)
    assert calls == [("경기도 수원시", "KakaoAK KEY")]


def test_geocode_region_falls_back_to_legacy_name(fake_kakao):
    calls = fake_kakao({"광주광역시 북구": FakeResponse({"documents": [doc("광주 북구", 126.912, 35.174)]})})
    assert kakao.geocode_region("전남광주통합특별시", "북구", "KEY") == (35.174, 126.912)
    assert [q for q, _ in calls] == ["전남광주통합특별시 북구", "광주광역시 북구"]


def test_geocode_region_ignores_other_regions(fake_kakao):
    # 검색 결과가 고른 시/군/구가 아니면 쓰지 않습니다
    fake_kakao({"경기도 광주시": FakeResponse({"documents": [doc("경기 하남시", 127.2, 37.5)]})})
    assert kakao.geocode_region("경기도", "광주시", "KEY") is None


@pytest.mark.parametrize(
    "response",
    [FakeResponse({"errorType": "AccessDeniedError"}, status=401), requests.ConnectionError("down")],
)
def test_geocode_region_failures_return_none(fake_kakao, response):
    calls = fake_kakao({"경기도 수원시": response})
    assert kakao.geocode_region("경기도", "수원시", "BAD") is None
    assert len(calls) == 1  # 키 오류·연결 오류는 다른 검색어로 다시 시도하지 않음
