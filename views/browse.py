import streamlit as st

from pawmatch import browse as B
from pawmatch import traits as T
from pawmatch.detail import render_dog_cards
from pawmatch.display import format_updated
from pawmatch.geo import REGION_CENTERS, ShelterLocator
from pawmatch.matching import breed_options
from pawmatch.regions import load_regions
from pawmatch.ui import inject_card_css, load_data_or_stop

PAGE_SIZE = 24  # 한 번에 보여줄 아이 수
COLUMNS = 4
WHOLE_COUNTRY, WHOLE_SIDO = "전국", "전체"
KEY = B.STATE_PREFIX  # 이 화면의 위젯 key 앞에 붙입니다


def reset_page() -> None:
    st.session_state[f"{KEY}limit"] = PAGE_SIZE


def reset_filters() -> None:
    """모든 조건을 처음 값으로 되돌립니다. (key를 지우기만 하면 화면의 입력값이 남아서 값을 직접 넣습니다)"""
    defaults = {
        "sido": WHOLE_COUNTRY, "keyword": "", "sizes": [], "ages": [], "sex": None, "statuses": [], "breeds": [],
        "order": B.RECENT, "limit": PAGE_SIZE,
    }  # fmt: skip
    for name, value in defaults.items():
        st.session_state[f"{KEY}{name}"] = value
    for key in [k for k in st.session_state if str(k).startswith(f"{KEY}sigungu_")]:
        st.session_state[key] = WHOLE_SIDO


def show_more() -> None:
    st.session_state[f"{KEY}limit"] = st.session_state.get(f"{KEY}limit", PAGE_SIZE) + PAGE_SIZE


def filter_controls(dogs: list[dict]) -> B.BrowseFilter:
    """검색 조건 입력칸을 보여주고, 고른 조건을 돌려줍니다."""
    regions = load_regions()
    with st.container(border=True):
        c1, c2, c3 = st.columns([1, 1, 2])
        sido = c1.selectbox(
            "시/도", [WHOLE_COUNTRY, *REGION_CENTERS], key=f"{KEY}sido", on_change=reset_page
        )
        sigungu_options = [WHOLE_SIDO, *regions.get(sido, ())]
        sigungu = c2.selectbox(
            "시/군/구", sigungu_options, key=f"{KEY}sigungu_{sido}", on_change=reset_page,
            disabled=len(sigungu_options) == 1,
        )  # fmt: skip
        keyword = c3.text_input(
            "검색어", key=f"{KEY}keyword", on_change=reset_page,
            placeholder="예: 온순, 갈색, 진도, 보호소 이름 (여러 낱말은 모두 포함)",
        )  # fmt: skip

        sizes = st.pills(
            "크기", list(B.SIZE_FILTER_LABELS), selection_mode="multi", format_func=B.SIZE_FILTER_LABELS.get,
            key=f"{KEY}sizes", on_change=reset_page,
            help="1살 미만 믹스견은 다 자란 크기를 알기 어려워 '크기 예측 어려움'으로 분류해요.",
        )  # fmt: skip

        c4, c5, c6 = st.columns([2, 1, 1.3])
        ages = c4.pills(
            "나이", list(T.AGE_LABELS), selection_mode="multi", format_func=T.AGE_LABELS.get,
            key=f"{KEY}ages", on_change=reset_page,
        )  # fmt: skip
        sex = c5.pills(
            "성별", ["M", "F"], format_func={"M": "수컷", "F": "암컷"}.get, key=f"{KEY}sex", on_change=reset_page
        )
        statuses = c6.pills(
            "상태", list(B.STATUS_LABELS), selection_mode="multi", format_func=B.STATUS_LABELS.get,
            key=f"{KEY}statuses", on_change=reset_page,
            help="공고 중: 원래 보호자가 찾아갈 수 있도록 기다리는 기간이에요. "
            "입양 가능: 공고가 끝나 입양을 문의할 수 있어요.",
        )  # fmt: skip
        breeds = breed_options(dogs)
        counts = dict(breeds)
        chosen_breeds = st.multiselect(
            "품종", [name for name, _ in breeds], format_func=lambda name: f"{name} ({counts[name]:,})",
            placeholder="모든 품종", key=f"{KEY}breeds", on_change=reset_page,
        )  # fmt: skip

        st.button("조건 초기화", on_click=reset_filters, type="tertiary", icon=":material/restart_alt:")

    return B.BrowseFilter(
        sido=None if sido == WHOLE_COUNTRY else sido,
        sigungu=None if sigungu == WHOLE_SIDO else sigungu,
        sizes=frozenset(sizes or ()),
        ages=frozenset(ages or ()),
        sex=sex,
        statuses=frozenset(statuses or ()),
        breeds=frozenset(chosen_breeds),
        keyword=keyword or "",
    )


st.title("🐶 보호견 둘러보기")
st.write("원하는 아이가 있다면 지역, 크기, 나이 같은 조건으로 직접 찾아보세요.")

inject_card_css()
data = load_data_or_stop()
st.caption(f"국가동물보호정보시스템 {format_updated(data.fetched_at)} · 공고 중 + 보호 중 {len(data.dogs):,}마리")

conditions = filter_controls(data.dogs)
found = B.filter_dogs(data.dogs, conditions)

# 입양 매칭 설문을 했다면 '나와 잘 맞는 순' 정렬과 적합도 점수를 함께 보여줍니다.
survey = st.session_state.get(B.MATCH_SURVEY_KEY)
sort_options = [o for o in B.SORT_LABELS if survey is not None or o != B.FIT]
if st.session_state.get(f"{KEY}order") not in sort_options:
    st.session_state[f"{KEY}order"] = B.RECENT

with st.container(border=True):
    if survey is None:
        st.markdown(
            "🏠 **내 생활 환경에 맞는 아이**가 궁금하다면 입양 매칭 설문을 해 보세요. "
            "설문 답변으로 여기서도 **나와 잘 맞는 순** 정렬과 적합도를 볼 수 있어요."
        )
        st.page_link("views/match.py", label="입양 매칭 설문 하러 가기", icon="🏠")
    else:
        sorted_by_fit = st.session_state.get(f"{KEY}order") == B.FIT
        st.markdown(
            "🏠 입양 매칭 설문 답변으로 **적합도**를 계산했어요. "
            + ("**나와 잘 맞는 순**으로 정렬했어요. " if sorted_by_fit else "정렬을 **나와 잘 맞는 순**으로 바꿔 보세요. ")
            + "(여기서는 지역을 조건으로 고르므로 거리는 점수에 넣지 않아요)"
        )
        st.page_link("views/match.py", label="설문 다시 하기", icon="🏠")

head, sort_col = st.columns([3, 1], vertical_alignment="bottom")
head.subheader(f"조건에 맞는 아이 {len(found):,}마리")
order = sort_col.selectbox(
    "정렬", sort_options, format_func=B.SORT_LABELS.get, key=f"{KEY}order", on_change=reset_page,
    label_visibility="collapsed",
)  # fmt: skip

if not found:
    st.info("조건에 맞는 아이가 없어요. 조건을 줄이거나 초기화해 보세요.")
    st.stop()

fits = B.fit_results(found, survey) if survey is not None else {}


def fit_badge(dog: dict) -> str | None:
    result = fits.get(str(dog.get("desertionNo")))
    return f":violet-badge[적합도 {result.score}점]" if result else None


def fit_detail(dog: dict) -> dict:
    result = fits.get(str(dog.get("desertionNo")))
    if result is None:
        return {}
    return {"score": result.score, "reasons": result.reasons, "cautions": result.cautions}


limit = min(st.session_state.get(f"{KEY}limit", PAGE_SIZE), len(found))
render_dog_cards(
    B.sort_dogs(found, order, fits=fits)[:limit], ShelterLocator(data.shelters), columns=COLUMNS, key_prefix="b",
    badge=fit_badge, detail_kwargs=fit_detail,
)  # fmt: skip

if limit < len(found):
    st.caption(f"{limit:,} / {len(found):,}마리를 보고 있어요.")
    st.button("더 보기", on_click=show_more, width="stretch")
