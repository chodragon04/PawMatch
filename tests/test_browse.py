# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""pawmatch.browse 단위 테스트 (조건 거르기, 정렬)."""

from datetime import date

from pawmatch import browse as B
from pawmatch import traits as T

TODAY = date(2026, 11, 4)


def dog(no, **kw):
    base = {
        "desertionNo": no, "kindNm": "믹스견", "age": "2020(년생)", "weight": "5(Kg)", "sexCd": "M",
        "careNm": "보호소", "careAddr": "경기도 수원시 영통구 광교호수로 234", "noticeSdt": "20261101",
        "noticeEdt": "20261111", "happenDt": "20261031", "specialMark": "", "colorCd": "흰색",
    }  # fmt: skip
    return {**base, **kw}


SUWON_SMALL = dog("1")
INCHEON_NO_COORDS = dog("2", careAddr="인천광역시 연수구 미추홀대로 340", careNm="좌표없는센터")  # 좌표 못 찾은 아이도 포함
BIG_FEMALE_ADOPTABLE = dog("3", weight="30(Kg)", sexCd="F", noticeEdt="20261030", noticeSdt="20261020",
                           happenDt="20261019", kindNm="진도견", specialMark="온순하고 사람을 좋아함")  # fmt: skip
PUPPY_MIX = dog("4", age="2026(60일미만)(년생)", weight="2(Kg)", noticeSdt="20261103", noticeEdt="20261104",
                happenDt="20261102", colorCd="갈색")  # fmt: skip
DOGS = [SUWON_SMALL, INCHEON_NO_COORDS, BIG_FEMALE_ADOPTABLE, PUPPY_MIX]


def ids(dogs):
    return [d["desertionNo"] for d in dogs]


def run(**kw):
    return ids(B.filter_dogs(DOGS, B.BrowseFilter(**kw), TODAY))


def test_no_conditions_keeps_everyone():
    assert run() == ["1", "2", "3", "4"]


def test_region_uses_shelter_address():
    assert run(sido="인천광역시") == ["2"]
    assert run(sido="인천광역시", sigungu="연수구") == ["2"]
    assert run(sido="경기도", sigungu="수원시") == ["1", "3", "4"]
    assert run(sido="부산광역시") == []


def test_size_age_sex_status_breed():
    assert run(sizes=frozenset({T.LARGE})) == ["3"]
    assert run(sizes=frozenset({B.UNKNOWN_SIZE})) == ["4"]  # 60일 미만 믹스견
    assert run(sizes=frozenset({T.SMALL, T.LARGE})) == ["1", "2", "3"]
    assert run(ages=frozenset({T.PUPPY})) == ["4"]
    assert run(sex="F") == ["3"]
    assert run(statuses=frozenset({B.ADOPTABLE})) == ["3"]
    assert run(statuses=frozenset({B.NOTICE})) == ["1", "2", "4"]  # 종료일 당일까지 공고 중
    assert run(breeds=frozenset({"진도견"})) == ["3"]


def test_keyword_matches_all_words_case_insensitive():
    assert run(keyword="온순") == ["3"]
    assert run(keyword="진도 온순") == ["3"]
    assert run(keyword="진도 갈색") == []
    assert run(keyword="  ") == ["1", "2", "3", "4"]
    assert run(keyword="좌표없는") == ["2"]


def test_conditions_combine():
    assert run(sido="경기도", sizes=frozenset({T.SMALL}), sex="M") == ["1"]


def test_notice_status():
    assert B.notice_status(SUWON_SMALL, TODAY) == B.NOTICE
    assert B.notice_status(BIG_FEMALE_ADOPTABLE, TODAY) == B.ADOPTABLE
    assert B.notice_status({}, TODAY) is None


def test_sort_orders():
    assert ids(B.sort_dogs(DOGS, B.RECENT, TODAY)) == ["4", "2", "1", "3"]  # 공고 시작일 최근 → 번호 큰 순
    assert ids(B.sort_dogs(DOGS, B.DEADLINE, TODAY)) == ["4", "1", "2", "3"]  # 오늘 마감 → 11/11 → 공고 끝난 아이
    assert ids(B.sort_dogs(DOGS, B.LONGEST, TODAY)) == ["3", "1", "2", "4"]  # 구조일 오래된 순


def test_fit_results_ignore_distance_and_breed_conditions():
    from pawmatch.matching import Survey

    survey = Survey(home="apartment", max_km=5.0, breeds=("푸들",))  # 둘러보기에서는 거리·품종 조건을 빼고 계산
    fits = B.fit_results(DOGS, survey, TODAY)
    assert set(fits) == {"1", "2", "3", "4"}
    assert all(r.parts["distance"] == 0.5 for r in fits.values())
    # 아파트 + 처음 키움(기본값): 대형견은 소형견보다 점수가 낮음
    assert fits["3"].score < fits["1"].score


def test_sort_by_fit_uses_scores_then_recent():
    from pawmatch.matching import Survey

    fits = B.fit_results(DOGS, Survey(home="apartment"), TODAY)
    ordered = ids(B.sort_dogs(DOGS, B.FIT, TODAY, fits=fits))
    scores = [fits[i].score for i in ordered]
    assert scores == sorted(scores, reverse=True)
    assert ordered[-2:] == ["3", "4"]  # 아파트에 대형견(3), 오래 혼자 두기 어려운 60일 미만 강아지(4)가 뒤로
    assert ids(B.sort_dogs(DOGS, B.FIT, TODAY)) == ids(B.sort_dogs(DOGS, B.RECENT, TODAY))  # 점수가 없으면 최근순


def test_sort_nearest_puts_unknown_distance_last():
    distances = {"1": 12.0, "2": None, "3": 3.5, "4": 12.0}
    # 가까운 순, 거리가 같으면 최근 등록순(4가 1보다 최근), 거리를 모르는 아이는 맨 뒤
    assert ids(B.sort_dogs(DOGS, B.NEAREST, TODAY, distances=distances)) == ["3", "4", "1", "2"]
    # 기준 위치가 없으면(거리 없음) 최근 등록순
    assert ids(B.sort_dogs(DOGS, B.NEAREST, TODAY)) == ids(B.sort_dogs(DOGS, B.RECENT, TODAY))


def test_keyword_finds_same_meaning_and_ignores_spacing():
    gentle = dog("11", specialMark="얌전함, 갈색 털")
    friendly = dog("12", specialMark="사람 좋아함")
    timid = dog("13", specialMark="소심함", colorCd="검정")
    hurt = dog("14", specialMark="다리 골절")
    pool = [gentle, friendly, timid, hurt]

    def find(kw):
        return ids(B.filter_dogs(pool, B.BrowseFilter(keyword=kw), TODAY))

    assert find("순한") == ["11"]  # 메모에 '순한'이 없어도 같은 뜻(얌전)이면 찾음
    assert find("사람좋아") == ["12"]  # 띄어쓰기 달라도 찾음
    assert find("사람 좋아") == ["12"]  # 두 낱말이 이어져야 뜻이 되는 말
    assert find("겁 많음") == ["13"]  # '많음'은 정도만 더하는 말
    assert find("온순 갈색") == ["11"]  # 성격과 털색 둘 다 맞아야 함
    assert find("피부") == []  # 건강은 글자 그대로만 (골절인 아이는 안 나옴)
