# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""유기견 상세 정보 창: 사진 캐러셀, 기본 정보, 특징 메모, 보호소 주소·연락처."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from urllib.parse import quote

import streamlit as st

from pawmatch.display import (
    adoption_status,
    dog_facts,
    format_age,
    format_breed,
    format_sex,
    format_shelter_hours,
    score_badge,
    status_badge,
)
from pawmatch.geo import ShelterLocator
from pawmatch.ui import carousel_html, photo_html

MASKED_TEL_RE = re.compile(r"^\*+$")

# 기본 정보: 왼쪽 회색 항목 이름, 오른쪽 값 (글머리표 목록 대신 표처럼)
FACTS_CSS = """
<style>
.pm-facts { display: grid; grid-template-columns: max-content 1fr; gap: 0.35rem 1rem; margin: 0.25rem 0 0.5rem; }
.pm-facts dt { color: var(--pm-muted); }
.pm-facts dd { margin: 0; word-break: keep-all; }
</style>
"""


def facts_html(facts: list[tuple[str, str]]) -> str:
    rows = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in facts)
    return f'{FACTS_CSS}<dl class="pm-facts">{rows}</dl>'


def kakao_map_link(address: str) -> str:
    """주소로 카카오맵 검색 화면을 여는 링크 (API 키 필요 없음)."""
    return f"https://map.kakao.com/link/search/{quote(address)}"


def shelter_contact(dog: dict, shelter: dict | None) -> dict:
    """보호소 이름·주소·전화·운영 시간. 유기견 정보 → 보호소 정보 순으로 채웁니다."""
    shelter = shelter or {}
    tel = (dog.get("careTel") or "").strip()
    if not tel or MASKED_TEL_RE.match(tel):
        tel = (shelter.get("careTel") or "").strip()
    if MASKED_TEL_RE.match(tel):
        tel = ""
    return {
        "name": (dog.get("careNm") or shelter.get("careNm") or "보호소").strip(),
        "address": (dog.get("careAddr") or shelter.get("careAddr") or "").strip(),
        "tel": tel,
        "hours": format_shelter_hours(shelter or None),
    }


def render_shelter_popover(contact: dict, distance_km: float | None) -> None:
    label = contact["name"] + (f" · {distance_km:.1f}km" if distance_km is not None else "")
    with st.popover(label, width="stretch"):
        st.markdown(f"**{contact['name']}**")
        if contact["address"]:
            st.markdown(f"{contact['address']}  \n[카카오맵에서 보기]({kakao_map_link(contact['address'])})")
        if contact["tel"]:
            digits = re.sub(r"[^\d+]", "", contact["tel"])
            st.markdown(f"전화 [{contact['tel']}](tel:{digits})")
        else:
            st.markdown("전화번호 정보 없음")
        for line in contact["hours"]:
            st.caption(line)


def render_dog_detail(
    dog: dict,
    shelter: dict | None = None,
    distance_km: float | None = None,
    score: int | None = None,
    reasons: list[str] | None = None,
    cautions: list[str] | None = None,
) -> None:
    left, right = st.columns([3, 2], gap="medium")
    with left:
        st.html(carousel_html(dog, f"detail-{dog.get('desertionNo') or id(dog)}"), unsafe_allow_javascript=True)
    with right:
        status = adoption_status(dog.get("noticeEdt"))
        badges = [status_badge(status)]
        if score is not None:
            badges.insert(0, score_badge(f"적합도 {score}점"))
        st.markdown(" ".join(badges))
        st.html(facts_html(dog_facts(dog)))
        render_shelter_popover(shelter_contact(dog, shelter), distance_km)

    memo = (dog.get("specialMark") or "").strip()
    if memo:
        st.markdown("**보호소 메모**")
        st.info(memo)
    if reasons:
        st.markdown("**잘 맞는 점**\n\n" + "\n".join(f"- {r}" for r in reasons))
    if cautions:
        st.markdown("**확인해 볼 점**\n\n" + "\n".join(f"- {c}" for c in cautions))


def open_detail(dog: dict, shelter: dict | None = None, **detail_kwargs) -> None:
    """유기견 상세 정보를 모달 창으로 엽니다. detail_kwargs는 render_dog_detail에 그대로 넘깁니다."""
    title = format_breed(dog)

    @st.dialog(title, width="large")
    def _dialog() -> None:
        render_dog_detail(dog, shelter, **detail_kwargs)

    _dialog()


def detail_button(dog: dict, locator: ShelterLocator, key: str, **detail_kwargs) -> None:
    """'자세히 보기' 버튼. 누르면 상세 정보 창을 엽니다."""
    if st.button("자세히 보기", key=key, width="stretch"):
        open_detail(dog, locator.shelter_info(dog), **detail_kwargs)


CARD_COLUMNS = 4  # PC에서 한 줄에 놓는 카드 수 (모든 화면 같음)

# 카드 배치: PC는 한 줄에 4장, 휴대폰(640px 이하)은 작은 카드를 한 줄에 2장 (사진 위, 글 아래).
# 매칭 이유 같은 메모는 휴대폰에서 세 줄까지만 보이고, 전체는 '자세히 보기'에 나옵니다.
CARD_CSS = """
<style>
[class*="st-key-pm_card_"] { gap: 0.45rem !important; }
[class*="st-key-pm_card_"] [data-testid="stMarkdownContainer"] p { margin-bottom: 0; }
@media (max-width: 640px) {
  [class*="st-key-pm_grid_"] [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; flex-direction: row !important;
                                                                 gap: 0.6rem !important; }
  [class*="st-key-pm_grid_"] [data-testid="stColumn"] { flex: 0 0 calc(50% - 0.3rem) !important;
                                                        width: calc(50% - 0.3rem) !important; min-width: 0 !important; }
  [class*="st-key-pm_card_"] { padding: 0.6rem !important; }
  [class*="st-key-pm_card_"] [data-testid="stMarkdownContainer"] p { font-size: 0.95rem; }
  [class*="st-key-pm_card_"] [data-testid="stCaptionContainer"] p { font-size: 0.8rem; line-height: 1.35; }
  [class*="_notes"] [data-testid="stCaptionContainer"] p { display: -webkit-box; -webkit-line-clamp: 3;
                                                           -webkit-box-orient: vertical; overflow: hidden; }
}
</style>
"""


def _card_body(
    dog: dict,
    locator: ShelterLocator,
    key: str,
    distance_km: float | None,
    show_shelter: bool,
    badge: str | None,
    notes: list[str],
    extra: dict,
) -> None:
    st.html(photo_html(dog, f"{key}-photo"), unsafe_allow_javascript=True)
    st.markdown(f"**{format_breed(dog)}**")
    lines = [f"{format_age(dog.get('age'))} · {format_sex(dog.get('sexCd'))}"]
    if show_shelter:
        shelter = (dog.get("careNm") or "").strip()
        lines.append(f"{shelter} · {distance_km:.1f}km" if distance_km is not None else shelter)
    st.caption("  \n".join(lines))
    badges = [b for b in (badge, status_badge(adoption_status(dog.get("noticeEdt")))) if b]
    st.markdown(" ".join(badges))
    if notes:
        with st.container(key=f"{key}_notes"):
            st.caption("  \n".join(notes))
    detail_button(dog, locator, key=f"{key}_detail", distance_km=distance_km, **extra)


def render_dog_cards(
    dogs: list[dict],
    locator: ShelterLocator,
    key_prefix: str = "dog",
    *,
    columns: int = CARD_COLUMNS,
    show_shelter: bool = True,
    distance_of: Callable[[dict], float | None] | None = None,
    badge: Callable[[dict], str | None] | None = None,
    notes: Callable[[dict], list[str]] | None = None,
    detail_kwargs: Callable[[dict], dict] | None = None,
) -> None:
    """유기견 카드 그리드. 모든 화면이 같은 카드를 씁니다.

    카드: 사진(하트) → 품종 → 나이·성별 / 보호소·거리 → 배지(점수, 공고 상태) → 메모(매칭 이유) → 자세히 보기.
    distance_of(dog)는 보호소까지 거리, badge(dog)는 점수 배지, notes(dog)는 카드에 보여줄 짧은 글 목록,
    detail_kwargs(dog)는 상세 창에 넘길 값입니다.
    """
    st.html(CARD_CSS)
    with st.container(key=f"pm_grid_{key_prefix}"):
        for start in range(0, len(dogs), columns):
            cols = st.columns(columns)
            for col, (i, dog) in zip(cols, enumerate(dogs[start : start + columns], start)):
                key = f"pm_card_{key_prefix}_{i}"
                with col, st.container(border=True, key=key):
                    _card_body(
                        dog, locator, key,
                        distance_km=distance_of(dog) if distance_of else None,
                        show_shelter=show_shelter,
                        badge=badge(dog) if badge else None,
                        notes=notes(dog) if notes else [],
                        extra=detail_kwargs(dog) if detail_kwargs else {},
                    )  # fmt: skip
