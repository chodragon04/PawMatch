"""pawmatch.display 단위 테스트."""

from datetime import date

import pytest

from pawmatch.api import dedupe_by_id
from pawmatch.display import adoption_status, format_age, format_sex, parse_ymd


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2026(60일미만)(년생)", "2026년생 · 60일 미만"),
        ("2024(년생)", "2024년생"),
        (" 2020 (년생) ", "2020년생"),
        ("", "나이 미상"),
        (None, "나이 미상"),
        ("알 수 없는 형식", "알 수 없는 형식"),
    ],
)
def test_format_age(raw, expected):
    assert format_age(raw) == expected


def test_format_sex():
    assert format_sex("M") == "수컷"
    assert format_sex("f") == "암컷"
    assert format_sex("Q") == "성별 미상"
    assert format_sex(None) == "성별 미상"


def test_parse_ymd():
    assert parse_ymd("20261102") == date(2026, 11, 2)
    assert parse_ymd("2026-11") is None
    assert parse_ymd(None) is None


def test_adoption_status():
    today = date(2026, 11, 3)
    assert adoption_status("20261102", today) == "입양 가능"
    assert adoption_status("20261103", today) == "공고 중 · 11/3까지"
    assert adoption_status("20261110", today) == "공고 중 · 11/10까지"
    assert adoption_status(None, today) == "보호 중"


def test_dedupe_by_id_keeps_first_and_items_without_id():
    dogs = [
        {"desertionNo": "1", "n": "a"},
        {"desertionNo": "2"},
        {"desertionNo": "1", "n": "b"},
        {"n": "no id"},
        {"n": "no id"},
    ]
    result = dedupe_by_id(dogs)
    assert [d.get("desertionNo") for d in result] == ["1", "2", None, None]
    assert result[0]["n"] == "a"
