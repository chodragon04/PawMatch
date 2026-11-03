"""유기견 상세 정보 창: 사진 캐러셀, 기본 정보, 특징 메모, 보호소 주소·연락처."""

from __future__ import annotations

import re
from urllib.parse import quote

import streamlit as st

from pawmatch.display import adoption_status, dog_facts, format_shelter_hours
from pawmatch.ui import carousel_html

MASKED_TEL_RE = re.compile(r"^\*+$")


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
    label = f"🏠 {contact['name']}" + (f" · {distance_km:.1f}km" if distance_km is not None else "")
    with st.popover(label, width="stretch"):
        st.markdown(f"**{contact['name']}**")
        if contact["address"]:
            st.markdown(f"📍 {contact['address']}  \n[카카오맵에서 보기]({kakao_map_link(contact['address'])})")
        if contact["tel"]:
            digits = re.sub(r"[^\d+]", "", contact["tel"])
            st.markdown(f"☎ [{contact['tel']}](tel:{digits})")
        else:
            st.markdown("☎ 연락처 정보가 없어요")
        for line in contact["hours"]:
            st.caption(f"🕘 {line}")
        st.caption("입양 문의 전에 운영 시간을 꼭 확인해 주세요.")


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
        badges = [f":{'green' if status == '입양 가능' else 'orange'}-badge[{status}]"]
        if score is not None:
            badges.insert(0, f":violet-badge[적합도 {score}점]")
        st.markdown(" ".join(badges))
        st.markdown("\n".join(f"- **{label}** {value}" for label, value in dog_facts(dog)))
        render_shelter_popover(shelter_contact(dog, shelter), distance_km)

    memo = (dog.get("specialMark") or "").strip()
    if memo:
        st.markdown("**보호소 메모**")
        st.info(memo)
    if reasons:
        st.markdown("**잘 맞는 이유**\n\n" + "\n".join(f"- 👍 {r}" for r in reasons))
    if cautions:
        st.markdown("**미리 알아두면 좋은 점**\n\n" + "\n".join(f"- ⚠️ {c}" for c in cautions))
    st.caption("점수와 정보는 보호소가 입력한 공공데이터를 바탕으로 해요. 입양 전 보호소에 꼭 확인해 주세요.")
