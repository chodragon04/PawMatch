import streamlit as st
from streamlit_js_eval import get_geolocation

from pawmatch.api import ApiError, fetch_all_dogs, fetch_shelters
from pawmatch.config import API_KEY_ENV, get_api_key
from pawmatch.geo import REGION_CENTERS, ShelterLocator, group_by_shelter, sort_by_distance
from pawmatch.ui import inject_card_css, render_grid

LATEST_COUNT = 8  # 위치가 없을 때 보여줄 최근 등록 아이 수
SHELTERS_STEP = 3  # 한 번에 보여줄 보호소 수
DOGS_PER_SHELTER = 4  # 보호소마다 먼저 보여줄 아이 수
MORE_DOGS_LIMIT = 20  # '더 보기'에서 추가로 보여줄 최대 아이 수
MY_LOCATION, PICK_REGION = "📍 내 위치로 찾기", "🗺️ 지역 선택"


@st.cache_data(ttl=3600, show_spinner=False)
def load_dogs(api_key: str) -> list[dict]:
    return fetch_all_dogs(api_key)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_shelters(api_key: str) -> list[dict]:
    return fetch_shelters(api_key)


def get_origin() -> tuple[float, float] | None:
    """사용자가 고른 방식으로 기준 위치를 정합니다."""
    mode = st.radio("기준 위치", [MY_LOCATION, PICK_REGION], horizontal=True, label_visibility="collapsed")

    if mode == PICK_REGION:
        region = st.selectbox("지역", list(REGION_CENTERS), index=0)
        st.caption(f"{region} 시청/도청 위치를 기준으로 거리를 계산합니다.")
        return REGION_CENTERS[region]

    st.caption("위치 정보는 가까운 보호소를 찾는 데에만 쓰이며 저장되지 않습니다.")
    loc = get_geolocation(component_key="user_geolocation")
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


def show_more_shelters() -> None:
    st.session_state.shelter_count = st.session_state.get("shelter_count", SHELTERS_STEP) + SHELTERS_STEP


def render_shelter_groups(groups: list[dict]) -> None:
    count = st.session_state.get("shelter_count", SHELTERS_STEP)
    for i, group in enumerate(groups[:count]):
        dogs = group["dogs"]
        with st.container(border=True):
            st.markdown(f"#### 🏠 {group['name']}")
            info = [f"📍 {group['distance_km']:.1f}km", f"아이들 {len(dogs)}마리"]
            if group["tel"]:
                info.append(f"☎ {group['tel']}")
            st.caption(" · ".join(info) + (f"\n\n{group['address']}" if group["address"] else ""))
            render_grid(dogs[:DOGS_PER_SHELTER], show_shelter=False, key_prefix=f"s{i}")

            rest = dogs[DOGS_PER_SHELTER:]
            if rest:
                with st.expander(f"이 보호소 아이들 {len(rest)}마리 더 보기"):
                    render_grid(rest[:MORE_DOGS_LIMIT], show_shelter=False, key_prefix=f"s{i}more")
                    if len(rest) > MORE_DOGS_LIMIT:
                        st.caption(
                            f"나머지 {len(rest) - MORE_DOGS_LIMIT}마리는 '보호견 둘러보기'에서 확인할 수 있어요."
                        )

    if count < len(groups):
        st.button("가까운 보호소 더 보기", on_click=show_more_shelters, width="stretch")


st.title("🐾 PawMatch")
st.subheader("사진과 생활 환경으로 찾는 유기견 입양 매칭")

st.write(
    "보호소에 있는 유기견을 사진이나 생활 환경을 기준으로 찾아볼 수 있는 웹서비스입니다. "
    "국가동물보호정보시스템의 구조동물 공공데이터를 활용합니다."
)

st.markdown(
    """
- **가까운 보호소 찾기** (이 화면): 내 위치나 고른 지역에서 가까운 보호소의 아이들부터 보기
- **보호견 둘러보기**: 지역, 크기, 나이 등 조건으로 검색
- **입양 매칭**: 간단한 설문으로 나와 잘 맞을 것 같은 아이 추천
- **사진으로 찾기**: 강아지 사진을 올리면 생김새가 비슷한 보호견 검색
"""
)

api_key = get_api_key()
if api_key is None:
    st.warning(
        f"공공데이터 API 키가 설정되지 않았습니다. `.env` 파일 또는 Streamlit Secrets에 "
        f"`{API_KEY_ENV}` 값을 넣어주세요."
    )
    st.stop()

inject_card_css()
st.divider()

try:
    with st.spinner("보호 중인 아이들을 불러오는 중..."):
        dogs = load_dogs(api_key)
except ApiError as exc:
    st.error(f"유기견 정보를 불러오지 못했습니다.\n\n{exc}")
    st.stop()

shelter_error = None
try:
    with st.spinner("보호소 위치를 불러오는 중..."):
        shelters = load_shelters(api_key)
except ApiError as exc:
    shelters, shelter_error = [], str(exc)

locator = ShelterLocator(shelters)

st.metric("지금 보호소에서 가족을 기다리는 아이들", f"{len(dogs):,}마리")
st.subheader("가까운 보호소의 아이들")

origin = get_origin()
if shelter_error:
    st.warning(f"보호소 위치 정보를 불러오지 못해 최근 등록순으로 보여드립니다.\n\n{shelter_error}")
    origin = None

if origin is not None:
    render_shelter_groups(group_by_shelter(sort_by_distance(dogs, locator, origin)))
else:
    st.caption("최근 등록된 아이들")
    render_grid(dogs[:LATEST_COUNT], key_prefix="latest")

with st.expander("🔧 데이터 연결 상태"):
    located = sum(1 for d in dogs if locator.locate(d))
    st.write(
        {
            "유기견 (공고 중 + 보호 중)": len(dogs),
            "보호소": len(shelters),
            "좌표가 있는 보호소": len(locator.by_reg_no) or len(locator.by_name),
            "보호소 좌표를 찾은 유기견": f"{located} / {len(dogs)}",
        }
    )
