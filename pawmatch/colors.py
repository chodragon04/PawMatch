# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""PawMatch 색 (한 곳에서 관리).

밝은 주황은 글자로 쓰면 흰 배경과의 대비가 2.35밖에 안 돼서 읽기 어렵습니다(웹 접근성 기준 4.5 이상).
그래서 쓰임새에 따라 주황을 세 가지로 나눠 씁니다.

- ORANGE: 면(주황 버튼 배경, 선택한 라디오 점 등). 테마의 primaryColor와 같은 값
- ORANGE_ICON: 아이콘·하트·켜진 탭 아이콘처럼 글자가 아닌 표시 (대비 3 이상)
- ORANGE_TEXT: 주황 글자 (흰 배경·연주황 배경 모두 대비 4.5 이상)

.streamlit/config.toml에도 같은 값이 들어 있습니다(설정 파일은 이 모듈을 읽을 수 없어서).
tests/test_colors.py가 두 곳의 값이 같은지, 대비가 기준을 넘는지 확인합니다.
"""

from __future__ import annotations

ORANGE = "#FF8A3D"  # 면: 주황 버튼 배경, 선택 표시
ORANGE_ICON = "#E0610B"  # 아이콘·하트·켜진 탭 아이콘 (흰 배경 대비 3.57)
ORANGE_TEXT = "#B8480E"  # 주황 글자 (흰 배경 5.29, 연주황 배경 4.89)
PEACH = "#FFF4EC"  # 연주황 배경 (사진 칸, 입력칸, 안내 상자)
PEACH_STRONG = "#FFEAD9"  # 점수 배지 배경 (진한 주황 글자 대비 4.54)
LINE = "#F3DCCB"  # 연한 주황 테두리 (하단 탭 윗선)
TEXT = "#3A2E2A"  # 본문 글자 (흰 배경 13.09)
MUTED = "#7A6A62"  # 흐린 글자: 캡션, 꺼진 탭, 빈 하트 (흰 배경 5.17, 연주황 배경 4.77)
WHITE = "#FFFFFF"

# CSS에서 var(--pm-…)로 쓰는 색. 모든 화면에 한 번 넣습니다(ui.render_nav_bar).
CSS_VARIABLES = {
    "--pm-orange": ORANGE,
    "--pm-orange-icon": ORANGE_ICON,
    "--pm-orange-text": ORANGE_TEXT,
    "--pm-peach": PEACH,
    "--pm-peach-strong": PEACH_STRONG,
    "--pm-line": LINE,
    "--pm-text": TEXT,
    "--pm-muted": MUTED,
}

ROOT_CSS = ":root { " + " ".join(f"{name}: {value};" for name, value in CSS_VARIABLES.items()) + " }"


def contrast(foreground: str, background: str) -> float:
    """두 색의 명도 대비 (WCAG 2.x 공식). 1~21, 글자는 4.5 이상, 아이콘·큰 글자는 3 이상이 기준입니다."""

    def luminance(hex_color: str) -> float:
        h = hex_color.lstrip("#")
        channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)
