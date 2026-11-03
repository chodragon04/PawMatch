"""기준 위치 고르기: 브라우저 위치(streamlit-js-eval) 또는 시/도 선택."""

from __future__ import annotations

import streamlit as st
from streamlit_js_eval import get_geolocation

from pawmatch.geo import REGION_CENTERS

MY_LOCATION, PICK_REGION = "📍 내 위치로 찾기", "🗺️ 지역 선택"


def pick_origin(key: str = "origin") -> tuple[float, float] | None:
    """사용자가 고른 방식으로 기준 위치(위도, 경도)를 정합니다. 정하지 못하면 None."""
    mode = st.radio(
        "기준 위치", [MY_LOCATION, PICK_REGION], horizontal=True, label_visibility="collapsed", key=f"{key}_mode"
    )

    if mode == PICK_REGION:
        region = st.selectbox("지역", list(REGION_CENTERS), index=0, key=f"{key}_region")
        st.caption(f"{region} 시청/도청 위치를 기준으로 거리를 계산합니다.")
        return REGION_CENTERS[region]

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
