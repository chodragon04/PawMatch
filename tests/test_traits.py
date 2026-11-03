"""pawmatch.traits 단위 테스트 (실데이터에서 본 값들로 확인)."""

from datetime import date

import pytest

from pawmatch import traits as T

TODAY = date(2026, 11, 3)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5.6(Kg)", 5.6),
        ("2(Kg)", 2.0),
        ("12..00(Kg)", 12.0),  # 점 두 개
        ("6,3(Kg)", 6.3),  # 쉼표
        ("1.8~2.0(Kg)", 1.9),  # 범위는 평균
        ("2500(Kg)", None),  # 말이 안 되는 값
        ("0(Kg)", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_weight(raw, expected):
    assert T.parse_weight(raw) == pytest.approx(expected) if expected else T.parse_weight(raw) is None


@pytest.mark.parametrize("weight, size", [(9.9, T.SMALL), (10, T.MEDIUM), (24.9, T.MEDIUM), (25, T.LARGE), (None, None)])
def test_size_from_weight(weight, size):
    assert T.size_from_weight(weight) == size


@pytest.mark.parametrize(
    "raw, group",
    [
        ("2026(60일미만)(년생)", T.PUPPY),
        ("2026(년생)", T.PUPPY),
        ("2025(년생)", T.YOUNG),
        ("2024(년생)", T.YOUNG),
        ("2023(년생)", T.ADULT),
        ("2019(년생)", T.ADULT),
        ("2018(년생)", T.SENIOR),
        ("나이 모름", None),
    ],
)
def test_age_group(raw, group):
    assert T.age_group(raw, TODAY) == group


@pytest.mark.parametrize(
    "memo, flags",
    [
        ("순하고 사람 좋아하는 프렌치불독", {T.GENTLE, T.FRIENDLY}),
        ("겁이많음, 사나움", {T.TIMID, T.AGGRESSIVE}),
        ("입질 없음", {T.GENTLE}),  # 부정하는 말이 오면 반대로
        ("겁은 많으나 순하고 공격성 없음", {T.TIMID, T.GENTLE}),
        ("심장사상충 양성,초록색목줄", {T.HEALTH}),
        ("심장사상충&파보 음성, 심장사상충약", set()),  # 음성 결과, 예방약
        ("피부가약간안좋은편", {T.HEALTH}),
        ("물건을 좋아함, 동물병원에서 구조", set()),  # '물'이 들어간 다른 단어
        ("활발 하며 하늘색 옷", {T.ACTIVE}),
        ("", set()),
    ],
)
def test_memo_traits_flags(memo, flags):
    assert set(T.memo_traits(memo).flags) == flags


def test_memo_traits_quotes_whole_phrase():
    traits = T.memo_traits("10-19, 칩없음, 착하고 사람 손길을 잘 따름. 목줄")
    assert traits.matches[T.GENTLE] == "착하고 사람 손길을 잘 따름"


def test_profile_uses_breed_for_puppies():
    maltese = T.profile({"kindNm": "말티즈", "age": "2026(60일미만)(년생)", "weight": "0.8(Kg)"}, TODAY)
    assert maltese.size == T.SMALL and not maltese.size_uncertain

    mixed = T.profile({"kindNm": "믹스견", "age": "2026(년생)", "weight": "3(Kg)"}, TODAY)
    assert mixed.size is None and mixed.size_uncertain

    tosa_mix = T.profile({"kindNm": "도사 믹스견", "age": "2026(년생)", "weight": "5(Kg)"}, TODAY)
    assert tosa_mix.size == T.LARGE


def test_profile_uses_weight_for_adults():
    p = T.profile({"kindNm": "믹스견", "age": "2020(년생)", "weight": "16(Kg)", "specialMark": "얌전"}, TODAY)
    assert p.size == T.MEDIUM and p.age_group == T.ADULT and p.energy == T.LOW


def test_energy_level():
    border = T.profile({"kindNm": "보더 콜리", "age": "2021(년생)", "weight": "18(Kg)"}, TODAY)
    senior = T.profile({"kindNm": "믹스견", "age": "2014(년생)", "weight": "8(Kg)"}, TODAY)
    assert border.energy == T.HIGH and senior.energy == T.LOW
