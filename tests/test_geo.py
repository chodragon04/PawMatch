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


def test_group_by_shelter_orders_by_distance_and_skips_unknown():
    from pawmatch.geo import group_by_shelter

    dogs = [
        {"desertionNo": "b1", "careRegNo": "222", "careNm": "부산 (사)보호소", "careTel": "051"},
        {"desertionNo": "s1", "careRegNo": "111", "careNm": "서울 보호소"},
        {"desertionNo": "b2", "careNm": "부산(사)보호소"},  # 번호 없이 이름만 있어도 같은 보호소
        {"desertionNo": "x", "careNm": "어딘가"},
    ]
    groups = group_by_shelter(sort_by_distance(dogs, ShelterLocator(SHELTERS), BUSAN))
    assert [g["name"] for g in groups] == ["부산 (사)보호소", "서울 보호소"]
    assert [d["desertionNo"] for d in groups[0]["dogs"]] == ["b1", "b2"]
    assert groups[0]["tel"] == "051" and groups[0]["distance_km"] < 5



@pytest.mark.parametrize(
    "address, area, expected",
    [
        ("인천광역시 연수구 미추홀대로 340", ("인천광역시", "연수구"), True),
        ("인천광역시 남동구 구월로 317 (만수동)", ("인천광역시", "연수구"), False),
        ("인천광역시 남동구 구월로 317 (만수동)", ("인천광역시", None), True),  # 시/군/구 '전체'
        ("경기도 수원시 영통구 광교호수로 234", ("경기도", "수원시"), True),  # 일반구가 있는 시
        ("강원도 춘천시 신북읍 신샘밭로 750", ("강원특별자치도", "춘천시"), True),  # 옛 이름
        ("전라남도 순천시 서면 운평리", ("전남광주통합특별시", "순천시"), True),  # 통합 전 이름
        ("광주광역시 북구 본촌동", ("전남광주통합특별시", "북구"), True),
        ("충남 천안시 동남구", ("충청남도", "천안시"), True),  # 줄임말
        ("세종특별자치시 전동면 미륵당1길 188", ("세종특별자치시", None), True),
        # 2026년 인천 개편 전 주소
        ("인천광역시 중구 개항로 68 (경동)", ("인천광역시", "제물포구"), True),
        ("인천광역시 중구 운남동로3번길 9 (운남동)", ("인천광역시", "영종구"), True),
        ("인천광역시 중구 운남동로3번길 9 (운남동)", ("인천광역시", "제물포구"), False),
        ("인천광역시 서구 가현산로23번길 36 (마전동)", ("인천광역시", "검단구"), True),
        ("인천광역시 서구 가정로 346 (가정동)", ("인천광역시", "서해구"), True),
        ("경기도 시흥시 뒷방울길 218", ("인천광역시", None), False),
        ("", ("인천광역시", "연수구"), False),
    ],
)
def test_address_in_area(address, area, expected):
    from pawmatch.geo import address_in_area

    assert address_in_area(address, *area) is expected


def test_group_by_shelter_puts_shelters_inside_area_first():
    from pawmatch.geo import group_by_shelter

    near_outside = {"careNm": "길동물병원", "careAddr": "인천광역시 남동구 구월로 317"}
    far_inside = {"careNm": "연수보호센터", "careAddr": "인천광역시 연수구 미추홀대로 340"}
    inside_no_coords = {"careNm": "좌표없는센터", "careAddr": "인천광역시 연수구 어딘가"}
    other_city = {"careNm": "시흥센터", "careAddr": "경기도 시흥시 뒷방울길 218"}
    ranked = [(near_outside, 2.0), (other_city, 3.0), (far_inside, 9.0), (inside_no_coords, None)]

    # 지역을 정하지 않으면 거리순, 좌표 없는 곳은 제외
    assert [g["name"] for g in group_by_shelter(ranked)] == ["길동물병원", "시흥센터", "연수보호센터"]

    # 연수구: 연수구 안(가까운 순, 좌표 없는 곳은 뒤) → 나머지 가까운 순
    groups = group_by_shelter(ranked, ("인천광역시", "연수구"))
    assert [(g["name"], g["in_area"]) for g in groups] == [
        ("연수보호센터", True), ("좌표없는센터", True), ("길동물병원", False), ("시흥센터", False),
    ]  # fmt: skip

    # 인천 전체: 인천 안 → 그다음 시흥
    groups = group_by_shelter(ranked, ("인천광역시", None))
    assert [g["name"] for g in groups] == ["길동물병원", "연수보호센터", "좌표없는센터", "시흥센터"]
