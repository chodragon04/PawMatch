import streamlit as st

from pawmatch.display import format_updated
from pawmatch.geo import ShelterLocator, group_by_shelter, sort_by_distance
from pawmatch.location import pick_origin, selected_area
from pawmatch.ui import inject_card_css, load_data_or_stop, page_header, render_grid

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
            st.markdown(f"#### {group['name']}")
            distance = group["distance_km"]
            info = [f":material/location_on: {distance:.1f}km" if distance is not None else "거리 정보 없음", f"아이들 {len(dogs)}마리"]
            if group["in_area"] and area:
                info.insert(0, f":material/push_pin: {area[1] or area[0]} 안")
            if group["tel"]:
                info.append(f":material/call: {group['tel']}")
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


# 다른 화면으로 가는 바로가기 카드 (카드 어디를 눌러도 이동)
SHORTCUTS = [
    ("views/browse.py", ":material/pets:", "보호견 둘러보기", "지역·크기·나이로 직접 찾기"),
    ("views/match.py", ":material/volunteer_activism:", "입양 매칭", "생활 환경에 맞는 아이 추천"),
    ("views/photo_search.py", ":material/photo_camera:", "사진으로 찾기", "닮은 아이를 사진으로 찾기"),
]  # fmt: skip
# 카드 안의 링크를 카드 전체로 넓혀서, 카드 어디를 눌러도 링크가 눌리게 합니다.
SHORTCUT_CSS = """
<style>
[class*="st-key-pm_short_"] { position: relative; gap: 0.1rem !important; }
[class*="st-key-pm_short_"] * { position: static !important; }
[class*="st-key-pm_short_"]:hover { border-color: #FF8A3D !important; background: #FFF4EC; }
[class*="st-key-pm_short_"] a[data-testid="stPageLink-NavLink"]::after { content: ""; position: absolute; inset: 0; z-index: 1; }
[class*="st-key-pm_short_"] a[data-testid="stPageLink-NavLink"] { padding: 0; background: transparent !important; }
[class*="st-key-pm_short_"] a[data-testid="stPageLink-NavLink"] p { font-size: 1.05rem; font-weight: 700; }
[class*="st-key-pm_short_"] a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] { color: #FF8A3D; font-size: 1.4rem; }
</style>
"""


def render_shortcuts() -> None:
    st.html(SHORTCUT_CSS)
    st.markdown("#### 이렇게도 찾아보세요")
    for i, (col, (path, icon, title, text)) in enumerate(zip(st.columns(len(SHORTCUTS)), SHORTCUTS)):
        with col, st.container(border=True, key=f"pm_short_{i}", gap=None):
            st.page_link(path, label=title, icon=icon)
            st.caption(text)


data = load_data_or_stop()
dogs, shelters = data.dogs, data.shelters
locator = ShelterLocator(shelters)

# 제목 옆에 작은 '소개' 버튼 (휴대폰에서도 줄바꿈하지 않음)
st.html("""<style>
.st-key-pm_home_head [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; align-items: center; }
.st-key-pm_home_head [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 1 1 auto !important; }
.st-key-pm_home_head [data-testid="stColumn"]:last-child { flex: 0 0 auto !important; }
</style>""")
with st.container(key="pm_home_head"):
    head, about = st.columns([4, 1], vertical_alignment="center")
with head:
    page_header(":primary[:material/pets:] PawMatch")
with about, st.popover("소개", icon=":material/info:", type="tertiary"):
    st.markdown("**사진과 생활 환경으로 찾는 유기견 입양 매칭**")
    st.write(
        "보호소에 있는 유기견을 사진이나 생활 환경을 기준으로 찾아볼 수 있는 웹서비스입니다. "
        "국가동물보호정보시스템의 구조동물 공공데이터를 활용합니다."
    )
    st.caption(f"국가동물보호정보시스템 {format_updated(data.fetched_at)}")
st.markdown(f"지금 가족을 기다리는 아이들 **:primary[{len(dogs):,}마리]**")

inject_card_css()
st.markdown("#### 가까운 보호소의 아이들")

origin = pick_origin("home")

if origin is not None:
    area = selected_area("home")
    groups = group_by_shelter(sort_by_distance(dogs, locator, origin), area)
    if area:
        name = area[1] or area[0]
        if any(g["in_area"] for g in groups):
            st.caption(f"{name} 보호소 먼저, 그다음 가까운 순이에요.")
        else:
            st.caption(f"{name}에는 보호 중인 아이가 없어서 가까운 순으로 보여드려요.")
    render_shelter_groups(groups, area)
else:
    st.caption("최근 등록된 아이들")
    render_grid(dogs[:LATEST_COUNT], key_prefix="latest")

# 목록을 다 본 사람에게 다른 찾기 방법을 소개 (하단 탭 아이콘만으로는 기능을 알기 어려워서)
st.divider()
render_shortcuts()
