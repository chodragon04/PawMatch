# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""pawmatch.matching 단위 테스트."""

from datetime import date

from pawmatch import matching as M

TODAY = date(2026, 11, 3)

CALM_SMALL_ADULT = {"desertionNo": "1", "kindNm": "믹스견", "age": "2019(년생)", "weight": "5(Kg)", "sexCd": "F",
                    "specialMark": "온순함, 사람을 잘 따름"}  # fmt: skip
BIG_ACTIVE_FIERCE = {"desertionNo": "2", "kindNm": "믹스견", "age": "2024(년생)", "weight": "30(Kg)", "sexCd": "M",
                     "specialMark": "활발, 사나움"}  # fmt: skip
NEWBORN_MIX = {"desertionNo": "3", "kindNm": "믹스견", "age": "2026(60일미만)(년생)", "weight": "2(Kg)", "sexCd": "M",
               "specialMark": ""}  # fmt: skip
SICK = {"desertionNo": "4", "kindNm": "믹스견", "age": "2020(년생)", "weight": "6(Kg)", "sexCd": "F",
        "specialMark": "심장사상충 양성"}  # fmt: skip

APARTMENT_BEGINNER = M.Survey(home=M.APARTMENT, walk=M.WALK_SHORT, first_dog=True, has_kids=True, away=M.AWAY_LONG)


def score(dog, survey=APARTMENT_BEGINNER, distance=None):
    return M.score_dog(dog, survey, distance, TODAY)


def test_score_is_between_0_and_100_and_weights_sum_to_100():
    assert sum(M.WEIGHTS.values()) == 100
    for dog in (CALM_SMALL_ADULT, BIG_ACTIVE_FIERCE, NEWBORN_MIX, SICK):
        assert 0 <= score(dog).score <= 100


def test_calm_small_dog_fits_apartment_beginner_better():
    good, bad = score(CALM_SMALL_ADULT), score(BIG_ACTIVE_FIERCE)
    assert good.score > bad.score + 30
    assert any("소형견" in r for r in good.reasons)
    assert any("사나움" in c for c in bad.cautions)


def test_big_active_dog_fits_yard_and_long_walks():
    yard = M.Survey(home=M.YARD, walk=M.WALK_LONG, first_dog=False, away=M.AWAY_SHORT)
    assert score(BIG_ACTIVE_FIERCE, yard).parts["size"] == 1.0
    assert score(BIG_ACTIVE_FIERCE, yard).parts["activity"] == 1.0
    assert score(BIG_ACTIVE_FIERCE, yard).score > score(BIG_ACTIVE_FIERCE).score


def test_unknown_information_is_neutral_not_penalized():
    result = score(NEWBORN_MIX)
    assert result.parts["size"] == M.NEUTRAL  # 다 자란 크기 모름
    assert result.parts["temperament"] == M.NEUTRAL  # 메모 없음
    assert result.parts["distance"] == M.NEUTRAL  # 위치 모름
    assert any("크기를 알기 어려워요" in c for c in result.cautions)


def test_newborn_is_hard_to_leave_alone():
    assert score(NEWBORN_MIX).parts["care"] < 0.2
    home_often = M.Survey(away=M.AWAY_SHORT)
    assert score(NEWBORN_MIX, home_often).parts["care"] == 1.0


def test_health_preference():
    assert score(SICK).parts["preference"] == 0.0
    willing = score(SICK, M.Survey(health_ok=True))
    assert willing.parts["preference"] == 1.0 and any("보살핌" in r for r in willing.reasons)


def test_preferences_match():
    survey = M.Survey(pref_sizes=("small",), pref_sex="F")
    assert score(CALM_SMALL_ADULT, survey).parts["preference"] == 1.0
    assert score(BIG_ACTIVE_FIERCE, survey).parts["preference"] == 0.0
    # 여러 개를 고르면 그중 하나만 맞아도 됨
    both = M.Survey(pref_sizes=("small", "large"), pref_ages=("adult", "senior"))
    assert score(CALM_SMALL_ADULT, both).parts["preference"] == 1.0
    assert score(BIG_ACTIVE_FIERCE, both).parts["preference"] == 0.5  # 크기는 맞고 나이(2024년생, 1~2살)는 다름


def test_closer_is_better():
    near, far = score(CALM_SMALL_ADULT, distance=3), score(CALM_SMALL_ADULT, distance=200)
    assert near.parts["distance"] > far.parts["distance"]
    assert any("가까운 보호소" in r for r in near.reasons)


def test_rank_dogs_orders_by_score_and_applies_max_distance():
    ranked = [(BIG_ACTIVE_FIERCE, 5.0), (CALM_SMALL_ADULT, 8.0), (NEWBORN_MIX, None), (SICK, 80.0)]
    results = M.rank_dogs(ranked, APARTMENT_BEGINNER, today=TODAY)
    assert results[0].dog is CALM_SMALL_ADULT
    assert [r.score for r in results] == sorted((r.score for r in results), reverse=True)

    within_10 = M.rank_dogs(ranked, M.Survey(max_km=10), today=TODAY)
    assert {r.dog["desertionNo"] for r in within_10} == {"1", "2"}  # 위치 모름, 80km 제외

    assert len(M.rank_dogs(ranked, APARTMENT_BEGINNER, limit=2, today=TODAY)) == 2


def test_breed_name_and_options():
    assert M.breed_name({"kindNm": "푸들"}) == "푸들"
    assert M.breed_name({"kindFullNm": "[개] 말티즈"}) == "말티즈"
    assert M.breed_name({}) == "기타"
    dogs = [{"kindNm": "믹스견"}, {"kindNm": "푸들"}, {"kindNm": "믹스견"}, {"kindNm": "말티즈"}]
    assert M.breed_options(dogs) == [("믹스견", 2), ("말티즈", 1), ("푸들", 1)]  # 많은 순, 같으면 가나다순


def test_rank_dogs_filters_by_breed():
    poodle = {**CALM_SMALL_ADULT, "desertionNo": "p", "kindNm": "푸들"}
    maltese = {**CALM_SMALL_ADULT, "desertionNo": "m", "kindNm": "말티즈"}
    ranked = [(BIG_ACTIVE_FIERCE, 5.0), (poodle, 8.0), (maltese, 9.0), (NEWBORN_MIX, None)]

    only_poodle = M.rank_dogs(ranked, M.Survey(breeds=("푸들",)), today=TODAY)
    assert [r.dog["desertionNo"] for r in only_poodle] == ["p"]

    two = M.rank_dogs(ranked, M.Survey(breeds=("푸들", "말티즈")), today=TODAY)
    assert {r.dog["desertionNo"] for r in two} == {"p", "m"}

    assert len(M.rank_dogs(ranked, M.Survey(), today=TODAY)) == 4  # 고르지 않으면 모든 품종
    assert M.rank_dogs(ranked, M.Survey(breeds=("셰퍼드",)), today=TODAY) == []
