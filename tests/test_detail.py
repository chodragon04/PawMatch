# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""상세 정보 창에 쓰는 함수 테스트 (display, ui.carousel_html, detail, geo.ShelterLocator.shelter_info)."""

from pawmatch.detail import kakao_map_link, shelter_contact
from pawmatch.display import dog_facts, format_neuter, format_shelter_hours, format_weight, format_ymd
from pawmatch.geo import ShelterLocator
from pawmatch.ui import carousel_html

DOG = {
    "desertionNo": "1", "kindFullNm": "[개] 말티즈", "age": "2019(년생)", "sexCd": "M", "weight": "4.8(Kg)",
    "colorCd": "흰색", "neuterYn": "Y", "happenDt": "20261102", "happenPlace": "관악구 관천로11길 11",
    "noticeSdt": "20261102", "noticeEdt": "20261112", "noticeNo": "서울-관악-2026-00225", "vaccinationChk": "",
    "careNm": "디아크 동물종합병원", "careRegNo": "311", "careTel": "02-816-7582",
    "careAddr": "서울특별시 동작구 장승배기로27길 18",
}  # fmt: skip
SHELTER = {"careNm": "디아크 동물종합병원", "careRegNo": "311", "careTel": "***********",
           "weekOprStime": "09:00", "weekOprEtime": "18:00", "weekendOprStime": ":", "weekendOprEtime": ":",
           "closeDay": "토요일+일요일+공휴일"}  # fmt: skip


def test_format_helpers():
    assert format_weight("4.8(Kg)") == "4.8kg" and format_weight("12..00(Kg)") == "12kg"
    assert format_weight("알수없음") == "알수없음" and format_weight("") == "체중 미상"
    assert format_neuter("Y") == "했어요" and format_neuter("U") == "확인 안 됨" and format_neuter(None) == "확인 안 됨"
    assert format_ymd("20261103") == "2026. 11. 3." and format_ymd("") == ""


def test_format_shelter_hours_skips_empty_values():
    assert format_shelter_hours(SHELTER) == ["평일 09:00 ~ 18:00", "휴무 토요일, 일요일, 공휴일"]
    assert format_shelter_hours({"closeDay": "0"}) == []
    assert format_shelter_hours(None) == []


def test_dog_facts_omits_missing_values():
    facts = dict(dog_facts(DOG))
    assert facts["체중"] == "4.8kg" and facts["중성화"] == "했어요"
    assert facts["발견"] == "2026. 11. 2. · 관악구 관천로11길 11"
    assert facts["공고 기간"] == "2026. 11. 2. ~ 2026. 11. 12."
    assert "접종" not in facts  # 빈 값은 빼기


def test_shelter_info_lookup():
    locator = ShelterLocator([SHELTER])
    assert locator.shelter_info(DOG) is SHELTER
    assert locator.shelter_info({"careNm": "디아크 동물종합병원"}) is SHELTER  # 번호가 없으면 이름으로
    assert locator.shelter_info({"careNm": "없는 곳"}) is None


def test_shelter_contact_prefers_unmasked_phone():
    contact = shelter_contact(DOG, SHELTER)
    assert contact["tel"] == "02-816-7582"  # 보호소 API의 가려진 번호(*****) 대신 유기견 정보의 번호
    assert contact["hours"] == ["평일 09:00 ~ 18:00", "휴무 토요일, 일요일, 공휴일"]
    assert shelter_contact({**DOG, "careTel": ""}, SHELTER)["tel"] == ""  # 둘 다 없으면 빈 값


def test_kakao_map_link_encodes_address():
    assert kakao_map_link("서울 동작구 1") == "https://map.kakao.com/link/search/%EC%84%9C%EC%9A%B8%20%EB%8F%99%EC%9E%91%EA%B5%AC%201"


def test_carousel_has_every_photo_and_escapes():
    dog = {"popfile1": "https://img/1.jpg", "popfile2": 'https://img/2.jpg?"><script>x()</script>',
           "kindFullNm": '<b>"믹스"</b>'}  # fmt: skip
    out = carousel_html(dog, "c1")
    assert out.count('class="pm-slide"') == 2 and out.count('class="pm-thumb"') == 2
    assert "x()</script>" not in out and '<b>"믹스' not in out  # 그대로 들어가면 안 됨
    assert "&lt;script&gt;x()" in out and "&lt;b&gt;" in out  # 이스케이프되어 들어감
    assert "pm-prev" in out and "pm-next" in out


def test_carousel_without_photos_shows_message():
    out = carousel_html({}, "c2")
    assert "pm-failed" in out and "사진을 불러오지 못했어요" in out and 'class="pm-slide"' not in out
