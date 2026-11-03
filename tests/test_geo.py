"""pawmatch.geo 단위 테스트."""

import pytest

from pawmatch.geo import REGION_CENTERS, ShelterLocator, haversine_km, sort_by_distance

SEOUL = REGION_CENTERS["서울특별시"]
BUSAN = REGION_CENTERS["부산광역시"]


def test_haversine_known_distance():
    # 서울시청 ~ 부산시청 직선거리 약 325km
    assert haversine_km(SEOUL, BUSAN) == pytest.approx(325, abs=10)
    assert haversine_km(SEOUL, SEOUL) == 0


SHELTERS = [
    {"careRegNo": "111", "careNm": "서울 보호소", "lat": "37.55", "lng": "126.97"},
    {"careRegNo": "222", "careNm": "부산 (사)보호소", "lat": "35.18", "lng": "129.07"},
    {"careRegNo": "333", "careNm": "좌표 없는 보호소", "lat": "", "lng": None},
]


def test_locator_matches_by_reg_no_then_name():
    loc = ShelterLocator(SHELTERS)
    assert loc.locate({"careRegNo": "111"}) == (37.55, 126.97)
    # 번호가 없거나 모르는 번호면 이름(공백/괄호 무시)으로 찾음
    assert loc.locate({"careRegNo": "999", "careNm": "부산 사 보호소"}) == (35.18, 129.07)
    assert loc.locate({"careNm": "부산(사)보호소"}) == (35.18, 129.07)
    assert loc.locate({"careRegNo": "333", "careNm": "좌표 없는 보호소"}) is None


def test_sort_by_distance_puts_nearest_first_and_unknown_last():
    dogs = [
        {"desertionNo": "busan", "careRegNo": "222"},
        {"desertionNo": "unknown", "careNm": "어딘가"},
        {"desertionNo": "seoul", "careRegNo": "111"},
    ]
    ranked = sort_by_distance(dogs, ShelterLocator(SHELTERS), SEOUL)
    assert [d["desertionNo"] for d, _ in ranked] == ["seoul", "busan", "unknown"]
    assert ranked[0][1] < 5 and ranked[2][1] is None

    from_busan = sort_by_distance(dogs, ShelterLocator(SHELTERS), BUSAN)
    assert from_busan[0][0]["desertionNo"] == "busan"
