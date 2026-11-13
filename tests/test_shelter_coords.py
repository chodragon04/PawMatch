# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""보호소 좌표 바로잡기 테스트 (카카오는 부르지 않고 응답을 흉내 냅니다)."""

import json

import pytest

from pawmatch import shelter_coords as C
from pawmatch.geo import ShelterLocator

JANGSU = {
    "careRegNo": "345475202600001", "careNm": "장수군 동물보호센터", "lat": 36.687443, "lng": 127.53412,
    "careAddr": "전북특별자치도 장수군 천천면 싸리재로 560  싸리재로 560, 도로 옆",
}  # fmt: skip
GEOCHANG = {"careRegNo": "348547202500001", "careNm": "거창군 동물보호소", "lat": 0.0, "lng": 0.0,
            "careAddr": "경상남도 거창군 거창읍 가실길 203  "}  # fmt: skip
OK = {"careRegNo": "1", "careNm": "수원시 동물보호센터", "lat": 37.2636, "lng": 127.0286,
      "careAddr": "경기도 수원시 영통구 광교호수로 234 (하동)"}  # fmt: skip


@pytest.mark.parametrize(
    "raw, cleaned",
    [
        ("전북특별자치도 장수군 천천면 싸리재로 560  싸리재로 560, 도로 옆", "전북특별자치도 장수군 천천면 싸리재로 560"),
        ("경기도 양주시 남면 감악산로 63-37 (남면) 한국동물구조관리협회", "경기도 양주시 남면 감악산로 63-37"),
        ("인천광역시 중구 운남동로3번길 9 (운남동)", "인천광역시 중구 운남동로3번길 9"),
        ("경기도 양주시 남면 상수리 410-1", "경기도 양주시 남면 상수리 410-1"),  # 지번 주소는 그대로
    ],
)
def test_clean_address(raw, cleaned):
    assert C.clean_address(raw) == cleaned


def test_address_variants_try_old_province_names():
    assert C.address_variants("전북특별자치도 장수군 천천면 싸리재로 560") == [
        "전북특별자치도 장수군 천천면 싸리재로 560", "전라북도 장수군 천천면 싸리재로 560",
    ]  # fmt: skip


def fake_kakao(places):
    """주소 → 좌표 사전으로 카카오 주소 검색을 흉내 냅니다."""
    calls = []

    def geocode(query):
        calls.append(query)
        hit = places.get(query)
        return (*hit, query) if hit else None

    return geocode, calls


def test_wrong_coordinates_are_fixed_and_correct_ones_kept():
    geocode, calls = fake_kakao({
        "전라북도 장수군 천천면 싸리재로 560": (35.6476, 127.5212),  # 카카오가 새 시/도 이름을 몰라 옛 이름으로 찾음
        "경상남도 거창군 거창읍 가실길 203": (35.6870, 127.9095),
        "경기도 수원시 영통구 광교호수로 234": (37.2640, 127.0290),
    })  # fmt: skip

    def no_place(query, must):
        return None

    jangsu, geochang, ok = (C.check_shelter(s, geocode, no_place) for s in (JANGSU, GEOCHANG, OK))
    assert jangsu.needs_fix and jangsu.diff_km > 100
    assert geochang.needs_fix and geochang.api is None  # 0,0은 좌표가 없는 것으로 봄
    assert not ok.needs_fix and ok.diff_km < C.FIX_KM
    assert calls[:2] == ["전북특별자치도 장수군 천천면 싸리재로 560", "전라북도 장수군 천천면 싸리재로 560"]

    payload = C.fixes_payload([jangsu, geochang, ok], "2026-11-13T00:00:00+00:00")
    assert sorted(payload["fixes"]) == sorted([GEOCHANG["careRegNo"], JANGSU["careRegNo"]])


def test_place_search_is_used_when_address_is_not_found():
    geocode, _ = fake_kakao({})
    asked = []

    def place(query, must):
        asked.append((query, must))
        return 35.65, 127.52, "장수군 동물보호센터"

    result = C.check_shelter(JANGSU, geocode, place)
    assert asked == [("장수군 장수군 동물보호센터", "장수군")] and result.needs_fix


def test_not_found_keeps_current_coordinates():
    geocode, _ = fake_kakao({})
    result = C.check_shelter(OK, geocode, lambda q, m: None)
    assert result.kakao is None and not result.needs_fix


def test_locator_uses_fix_only_while_address_is_the_same(tmp_path):
    fixes = {JANGSU["careRegNo"]: {"address": C.normalize_address(JANGSU["careAddr"]), "lat": 35.6476, "lng": 127.5212}}
    assert C.shelter_coords(JANGSU, fixes) == (35.6476, 127.5212)
    moved = {**JANGSU, "careAddr": "전북특별자치도 장수군 장수읍 새주소로 1"}
    assert C.shelter_coords(moved, fixes) == (JANGSU["lat"], JANGSU["lng"])  # 이사했으면 예전에 고친 좌표를 안 씀
    assert C.shelter_coords(GEOCHANG, {}) is None  # 0,0은 쓰지 않음

    path = tmp_path / "fixes.json"
    path.write_text(json.dumps({"fixes": fixes}), encoding="utf-8")
    assert C.load_fixes(path)[JANGSU["careRegNo"]]["lat"] == 35.6476


def test_shelter_locator_applies_fixes(monkeypatch):
    fixes = {JANGSU["careRegNo"]: {"address": C.normalize_address(JANGSU["careAddr"]), "lat": 35.6476, "lng": 127.5212}}
    monkeypatch.setattr(C, "load_fixes", lambda: fixes)
    locator = ShelterLocator([JANGSU, GEOCHANG, OK])
    assert locator.locate({"careRegNo": JANGSU["careRegNo"]}) == (35.6476, 127.5212)
    assert locator.locate({"careRegNo": GEOCHANG["careRegNo"], "careNm": "거창군 동물보호소"}) is None
    assert locator.locate({"careRegNo": "1"}) == (37.2636, 127.0286)
