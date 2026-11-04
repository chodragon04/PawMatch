import streamlit as st

from pawmatch.data import STORE
from pawmatch.display import format_updated
from pawmatch.geo import ShelterLocator, group_by_shelter, sort_by_distance
from pawmatch.location import pick_origin, selected_area
from pawmatch.ui import inject_card_css, load_data_or_stop, render_grid

LATEST_COUNT = 8  # 위치가 없을 때 보여줄 최근 등록 아이 수
SHELTERS_STEP = 3  # 한 번에 보여줄 보호소 수
DOGS_PER_SHELTER = 4  # 보호소마다 먼저 보여줄 아이 수
MORE_DOGS_LIMIT = 20  # '더 보기'에서 추가로 보여줄 최대 아이 수


def show_more_shelters() -> None:
    st.session_state.shelter_count = st.session_state.get("shelter_count", SHELTERS_STEP) + SHELTERS_STEP


def render_shelter_groups(groups: list[dict], area: tuple[str, str] | None = None) -> None:
    count = st.session_state.get("shelter_count", SHELTERS_STEP)
    for i, group in enumerate(groups[:count]):
        dogs = group["dogs"]
        with st.container(border=True):
            st.markdown(f"#### 🏠 {group['name']}")
            distance = group["distance_km"]
            info = [f"📍 {distance:.1f}km" if distance is not None else "📍 거리 정보 없음", f"아이들 {len(dogs)}마리"]
            if group["in_area"] and area:
                info.insert(0, f"📌 {area[1] or area[0]} 안")
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

# 다른 화면으로 가는 바로가기 카드
SHORTCUTS = [
    ("views/browse.py", "🐶", "보호견 둘러보기", "원하는 아이가 있다면 지역, 크기, 나이, 품종 같은 조건으로 직접 찾아보세요."),
    ("views/match.py", "🏠", "입양 매칭", "어떤 아이가 맞을지 모르겠다면 생활 환경을 알려주세요. 잘 맞는 아이와 그 이유를 알려드려요."),
    ("views/photo_search.py", "📷", "사진으로 찾기", "강아지 사진을 올리거나 찍으면 생김새가 비슷한 보호견을 찾아드려요."),
]  # fmt: skip
for col, (path, icon, title, text) in zip(st.columns(len(SHORTCUTS)), SHORTCUTS):
    with col, st.container(border=True, height="stretch"):
        st.markdown(f"#### {icon} {title}")
        st.write(text)
        st.page_link(path, label=f"{title} 바로 가기", icon=":material/arrow_forward:")
st.caption("아래에서는 내 위치나 고른 지역에서 가까운 보호소의 아이들을 먼저 볼 수 있어요.")

inject_card_css()
st.divider()

data = load_data_or_stop()
dogs, shelters = data.dogs, data.shelters
locator = ShelterLocator(shelters)

st.metric("지금 보호소에서 가족을 기다리는 아이들", f"{len(dogs):,}마리")
st.caption(f"국가동물보호정보시스템 {format_updated(data.fetched_at)}")
st.subheader("가까운 보호소의 아이들")

origin = pick_origin("home")

if origin is not None:
    area = selected_area("home")
    groups = group_by_shelter(sort_by_distance(dogs, locator, origin), area)
    if area:
        name = area[1] or area[0]
        if any(g["in_area"] for g in groups):
            st.caption(f"📌 {name} 안에 있는 보호소를 먼저 보여드리고, 그다음 가까운 보호소 순으로 보여드려요.")
        else:
            st.caption(f"{name} 안에는 지금 보호 중인 아이가 있는 보호소가 없어 가까운 보호소 순으로 보여드려요.")
    render_shelter_groups(groups, area)
else:
    st.caption("최근 등록된 아이들")
    render_grid(dogs[:LATEST_COUNT], key_prefix="latest")

with st.expander("🔧 데이터 연결 상태"):
    located = sum(1 for d in dogs if locator.locate(d))
    st.write(
        {
            "데이터 출처": {"snapshot": "저장된 스냅샷", "api": "API 직접 호출"}.get(data.source, data.source),
            "데이터 시각": format_updated(data.fetched_at),
            "뒤에서 새로 받는 중": STORE.refreshing,
            "마지막 새로 받기 오류": STORE.last_error or "없음",
            "유기견 (공고 중 + 보호 중)": len(dogs),
            "보호소": len(shelters),
            "좌표가 있는 보호소": len(locator.by_reg_no) or len(locator.by_name),
            "보호소 좌표를 찾은 유기견": f"{located} / {len(dogs)}",
        }
    )
