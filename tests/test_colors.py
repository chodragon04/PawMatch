# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""색 테스트: 글자·아이콘 색이 대비 기준을 넘는지, 설정 파일과 colors.py의 값이 같은지."""

from pathlib import Path

import pytest
import tomllib

from pawmatch import colors as C

CONFIG = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"


@pytest.mark.parametrize(
    "foreground, background, minimum",
    [
        (C.TEXT, C.WHITE, 4.5),  # 본문
        (C.MUTED, C.WHITE, 4.5),  # 캡션, 꺼진 탭 글자
        (C.MUTED, C.PEACH, 4.5),  # 연주황 칸 위 흐린 글자
        (C.ORANGE_TEXT, C.WHITE, 4.5),  # 주황 글자 (마릿수, 켜진 탭, 확인해 볼 점, 링크)
        (C.ORANGE_TEXT, C.PEACH, 4.5),
        (C.ORANGE_TEXT, C.PEACH_STRONG, 4.5),  # 점수 배지
        (C.ORANGE_ICON, C.WHITE, 3.0),  # 아이콘·하트 (글자가 아닌 표시는 3 이상)
        (C.TEXT, C.ORANGE, 4.5),  # 주황 버튼 위 글자
        (C.TEXT, C.PEACH, 4.5),  # 안내 상자
    ],
)
def test_contrast_meets_wcag_aa(foreground, background, minimum):
    assert C.contrast(foreground, background) >= minimum


def test_bright_orange_is_not_for_text():
    """밝은 주황은 글자로 쓰면 기준(4.5)을 못 넘어서 면에만 씁니다."""
    assert C.contrast(C.ORANGE, C.WHITE) < 3


def test_streamlit_theme_uses_the_same_colors():
    theme = tomllib.loads(CONFIG.read_text(encoding="utf-8"))["theme"]
    assert theme["primaryColor"] == C.ORANGE
    assert theme["secondaryBackgroundColor"] == C.PEACH
    assert theme["textColor"] == C.TEXT
    assert theme["orangeTextColor"] == theme["linkColor"] == C.ORANGE_TEXT
    assert theme["orangeBackgroundColor"] == C.PEACH_STRONG
    assert (theme["blueColor"], theme["blueTextColor"], theme["blueBackgroundColor"]) == (C.ORANGE_ICON, C.TEXT, C.PEACH)


def test_css_variables_are_defined_once():
    assert C.ROOT_CSS.startswith(":root {")
    assert all(f"{name}: {value};" in C.ROOT_CSS for name, value in C.CSS_VARIABLES.items())
