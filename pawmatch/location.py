"""기준 위치 고르기: 브라우저 위치(streamlit-js-eval) 또는 시/도 → 시/군/구 선택."""

from __future__ import annotations

import streamlit as st
from streamlit_js_eval import get_geolocation

from pawmatch.config import get_kakao_key
from pawmatch.geo import REGION_CENTERS
from pawmatch.kakao import geocode_region
from pawmatch.regions import load_regions

MY_LOCATION, PICK_REGION = "📍 내 위치로 찾기", "🗺️ 지역 선택"
WHOLE_SIDO = "전체"


@st.cache_data(ttl=7 * 24 * 3600, show_spinner=False)
def _cached_geocode(sido: str, sigungu: str, api_key: str) -> tuple[float, float]:
    pos = geocode_region(sido, sigungu, api_key)
    if pos is None:  # 실패한 결과는 캐시하지 않고 다음에 다시 시도합니다
        raise LookupError(f"{sido} {sigungu}")
    return pos


def locate_sigungu(sido: str, sigungu: str) -> tuple[float, float] | None:
    """시/군/구 중심 좌표. 카카오 API 키가 없거나 찾지 못하면 None."""
    api_key = get_kakao_key()
    if not api_key:
        return None
    try:
        return _cached_geocode(sido, sigungu, api_key)
    except LookupError:
        return None


def selected_area(key: str) -> tuple[str, str | None] | None:
    """지역 선택에서 고른 (시/도, 시/군/구). 시/군/구가 '전체'면 (시/도, None), 내 위치를 쓰면 None."""
    return st.session_state.get(f"{key}_area")


def pick_region(key: str) -> tuple[float, float]:
    """시/도와 시/군/구를 고르게 하고 기준 위치를 돌려줍니다."""
    regions = load_regions()
    col_sido, col_sigungu = st.columns(2)
    sido = col_sido.selectbox("시/도", list(REGION_CENTERS), index=0, key=f"{key}_region")
    options = [WHOLE_SIDO, *regions.get(sido, ())]
    # 시/도가 바뀌면 시/군/구 선택을 처음(전체)으로 되돌리도록 key에 시/도를 넣습니다.
    sigungu = col_sigungu.selectbox(
        "시/군/구", options, index=0, key=f"{key}_sigungu_{sido}", disabled=len(options) == 1
    )
    st.session_state[f"{key}_area"] = (sido, sigungu if sigungu != WHOLE_SIDO else None)

    if sigungu != WHOLE_SIDO:
        pos = locate_sigungu(sido, sigungu)
        if pos is not None:
            st.caption(f"{sido} {sigungu} 위치를 기준으로 거리를 계산합니다.")
            return pos
        st.caption(f"{sigungu} 위치를 찾지 못해 {sido} 시청/도청 위치를 기준으로 거리를 계산합니다.")
        return REGION_CENTERS[sido]

    st.caption(f"{sido} 시청/도청 위치를 기준으로 거리를 계산합니다.")
    return REGION_CENTERS[sido]


def pick_origin(key: str = "origin") -> tuple[float, float] | None:
    """사용자가 고른 방식으로 기준 위치(위도, 경도)를 정합니다. 정하지 못하면 None."""
    mode = st.radio(
        "기준 위치", [MY_LOCATION, PICK_REGION], horizontal=True, label_visibility="collapsed", key=f"{key}_mode"
    )

    if mode == PICK_REGION:
        return pick_region(key)
    st.session_state[f"{key}_area"] = None

    st.caption("위치 정보는 가까운 보호소를 찾는 데에만 쓰이며 저장되지 않습니다.")
    loc = get_geolocation(component_key=f"{key}_geolocation")
    if loc is None:
        st.info("브라우저에서 위치 권한을 허용해 주세요. 허용하지 않으려면 '지역 선택'을 이용하세요.")
        return None
    if "error" in loc:
        message = (loc.get("error") or {}).get("message", "")
        st.warning(f"위치를 가져오지 못했습니다. '지역 선택'을 이용해 주세요. ({message})")
        return None
    coords = loc.get("coords") or {}
    if coords.get("latitude") is None or coords.get("longitude") is None:
        return None
    return coords["latitude"], coords["longitude"]
