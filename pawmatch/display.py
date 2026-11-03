"""API 원문 값을 화면에 보여주기 좋은 문구로 바꾸는 함수들."""

from __future__ import annotations

import re
from datetime import date

_AGE_RE = re.compile(r"^\s*(\d{4})\s*(?:\((?!년생)([^)]*)\))?\s*\(년생\)\s*$")

SEX_LABELS = {"M": "수컷", "F": "암컷", "Q": "성별 미상"}


def format_age(raw: str | None) -> str:
    """'2026(60일미만)(년생)' -> '2026년생 · 60일 미만', '2024(년생)' -> '2024년생'."""
    if not raw:
        return "나이 미상"
    m = _AGE_RE.match(raw)
    if not m:
        return raw.strip()
    year, note = m.groups()
    if note:
        note = note.replace("미만", " 미만").replace("이상", " 이상").replace("  ", " ").strip()
        return f"{year}년생 · {note}"
    return f"{year}년생"


def format_sex(code: str | None) -> str:
    return SEX_LABELS.get((code or "").upper(), "성별 미상")


def parse_ymd(raw: str | None) -> date | None:
    """'20261102' -> date(2026, 11, 2). 형식이 맞지 않으면 None."""
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))  # type: ignore[index]
    except (TypeError, ValueError):
        return None


def adoption_status(notice_end: str | None, today: date | None = None) -> str:
    """공고 종료일 기준 상태 문구.

    공고 기간에는 원래 보호자가 찾아갈 수 있도록 기다리고, 기간이 끝나면 입양을 문의할 수 있습니다.
    """
    today = today or date.today()
    end = parse_ymd(notice_end)
    if end is None:
        return "보호 중"
    if end >= today:
        return f"공고 중 · {end.month}/{end.day}까지"
    return "입양 가능"
