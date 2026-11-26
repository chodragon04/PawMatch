# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
from dataclasses import replace

import streamlit as st

from pawmatch import browse as B
from pawmatch import state as S
from pawmatch import traits as T
from pawmatch.detail import render_dog_cards
from pawmatch.display import chips_markdown, format_updated, score_badge
from pawmatch.geo import REGION_CENTERS, ShelterLocator, haversine_km
from pawmatch.location import PICK_REGION, locate_sigungu, remembered_location, request_my_location
from pawmatch.matching import ANY, breed_options
from pawmatch.regions import load_regions
from pawmatch.ui import inject_card_css, is_phone, load_data_or_stop, page_header

PAGE_SIZE = 24  # 한 번에 보여줄 아이 수
WHOLE_COUNTRY, WHOLE_SIDO = "전국", "전체"
KEY = S.BROWSE  # 이 화면의 입력칸 key 앞에 붙입니다
KEEP = {"persist_state": S.PERSIST}  # 다른 화면에 갔다 와도 입력값 유지


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


def carry_to_match(c: B.BrowseFilter) -> None:
    """둘러보기 조건(지역, 크기, 나이, 성별, 품종)을 입양 매칭 화면의 입력칸에 넣습니다."""
    K, ss = S.match_key, st.session_state
    taken: list[str] = []
    if c.sido:
        ss[K("mode")] = PICK_REGION
        ss[K("region")] = c.sido
        ss[f"{K('sigungu')}_{c.sido}"] = c.sigungu or WHOLE_SIDO
        taken.append(f"{c.sido} {c.sigungu or ''}".strip())
    sizes = [x for x in T.SIZE_LABELS if x in c.sizes]  # '크기 예측 어려움'은 매칭에 없는 조건
    ages = [a for a in T.AGE_LABELS if a in c.ages]
    breeds = list(c.breeds)
    ss[K("sizes")], ss[K("ages")], ss[K("sex")], ss[K("breeds")] = sizes, ages, c.sex, breeds
    taken += [T.SIZE_LABELS[x] for x in sizes] + [T.AGE_LABELS[a] for a in ages]
    taken += [{"M": "수컷", "F": "암컷"}[c.sex]] if c.sex else []
    taken += breeds

    survey = ss.get(S.MATCH_SURVEY)
    if survey is not None:  # 이미 설문을 했다면 결과에 바로 반영
        ss[S.MATCH_SURVEY] = replace(
            survey, pref_sizes=tuple(sizes), pref_ages=tuple(ages), pref_sex=c.sex or ANY, breeds=tuple(breeds)
        )
    message = f"둘러보기 조건을 가져왔어요: {' · '.join(taken)}." if taken else "둘러보기에서 왔어요."
    message += " 결과에 바로 반영했어요." if survey is not None else " 생활 환경 질문에 답하고 아래 버튼을 눌러 주세요."
    if c.keyword or c.statuses or B.UNKNOWN_SIZE in c.sizes:
        message += " (검색어·상태·'크기 예측 어려움'은 입양 매칭에 없는 조건이라 빼고 가져왔어요)"
    ss[S.MATCH_NOTICE] = message


def filters_start_open() -> bool:
    """검색 조건을 처음에 펼쳐 둘지. 휴대폰은 결과가 먼저 보이게 접어 두고, 화면이 넓은 PC는 펼쳐 둡니다."""
    return not is_phone()


def chosen_labels(c: B.BrowseFilter) -> list[str]:
    """고른 조건을 짧은 글로 (접힌 검색 조건 아래 요약 칩)."""
    labels = [f"{c.sido} {c.sigungu or ''}".strip()] if c.sido else []
    labels += [f"‘{c.keyword.strip()}’"] if c.keyword.strip() else []
    labels += [T.SIZE_LABELS.get(x, "크기 예측 어려움") for x in B.SIZE_FILTER_LABELS if x in c.sizes]
    labels += [T.AGE_LABELS[a] for a in T.AGE_LABELS if a in c.ages]
    labels += [{"M": "수컷", "F": "암컷"}[c.sex]] if c.sex else []
    labels += [B.STATUS_LABELS[x] for x in B.STATUS_LABELS if x in c.statuses]
    breeds = sorted(c.breeds)
    labels += breeds if len(breeds) <= 2 else [*breeds[:2], f"품종 {len(breeds) - 2}개 더"]
    return labels


def nearest_origin(c: B.BrowseFilter) -> tuple[tuple[float, float] | None, str]:
    """'가까운 순'의 기준 위치와 설명.

    1) 홈·매칭에서 30분 안에 받은 내 위치 → 2) 검색 조건에서 고른 시/군/구(또는 시/도) 중심
    → 3) 둘 다 없으면 지금 브라우저에 내 위치를 물어봅니다. (사용자가 '가까운 순'을 골랐을 때만)
    """
    remembered = remembered_location()
    if remembered is not None:
        return (remembered[0], remembered[1]), "내 위치"
    if c.sido:
        pos = locate_sigungu(c.sido, c.sigungu) if c.sigungu else None
        if pos is not None:
            return pos, f"{c.sido} {c.sigungu}"
        return REGION_CENTERS[c.sido], f"{c.sido} 시청·도청"
    got = request_my_location()
    if isinstance(got, tuple):
        return got, "내 위치"
    if isinstance(got, str):  # 브라우저 오류 문구는 영어라 보여주지 않음
        return None, "내 위치를 가져오지 못했어요. 검색 조건에서 시/도를 고르면 그 지역 기준으로 보여드려요."
    return None, "가까운 순으로 보려면 위치 권한을 허용해 주세요. 검색 조건에서 시/도를 골라도 돼요."


def filter_controls(dogs: list[dict], survey) -> B.BrowseFilter:
    """검색 조건 입력칸(접을 수 있음)을 보여주고, 고른 조건을 돌려줍니다."""
    regions = load_regions()
    with st.expander("검색 조건", expanded=filters_start_open(), key=f"{KEY}filters", icon=":material/tune:"):
        c1, c2, c3 = st.columns([1, 1, 2])
        sido = c1.selectbox(
            "시/도", [WHOLE_COUNTRY, *REGION_CENTERS], key=f"{KEY}sido", on_change=reset_page, **KEEP
        )
        sigungu_options = [WHOLE_SIDO, *regions.get(sido, ())]
        sigungu = c2.selectbox(
            "시/군/구", sigungu_options, key=f"{KEY}sigungu_{sido}", on_change=reset_page,
            disabled=len(sigungu_options) == 1, **KEEP,
        )  # fmt: skip
        keyword = c3.text_input(
            "검색어", key=f"{KEY}keyword", on_change=reset_page, **KEEP,
            placeholder="예: 온순, 갈색, 진도, 보호소 이름 (여러 낱말은 모두 포함)",
        )  # fmt: skip

        sizes = st.pills(
            "크기", list(B.SIZE_FILTER_LABELS), selection_mode="multi", format_func=B.SIZE_FILTER_LABELS.get,
            key=f"{KEY}sizes", on_change=reset_page, **KEEP,
            help="1살 미만 믹스견은 다 자란 크기를 알기 어려워 '크기 예측 어려움'으로 분류해요.",
        )  # fmt: skip

        c4, c5, c6 = st.columns([2, 1, 1.3])
        ages = c4.pills(
            "나이", list(T.AGE_LABELS), selection_mode="multi", format_func=T.AGE_LABELS.get,
            key=f"{KEY}ages", on_change=reset_page, **KEEP,
        )  # fmt: skip
        sex = c5.pills(
            "성별", ["M", "F"], format_func={"M": "수컷", "F": "암컷"}.get, key=f"{KEY}sex", on_change=reset_page,
            **KEEP,
        )
        statuses = c6.pills(
            "상태", list(B.STATUS_LABELS), selection_mode="multi", format_func=B.STATUS_LABELS.get,
            key=f"{KEY}statuses", on_change=reset_page, **KEEP,
            help="공고 중: 원래 보호자가 찾아갈 수 있도록 기다리는 기간이에요. "
            "입양 가능: 공고가 끝나 입양을 문의할 수 있어요.",
        )  # fmt: skip
        breeds = breed_options(dogs)
        counts = dict(breeds)
        chosen_breeds = st.multiselect(
            "품종", [name for name, _ in breeds], format_func=lambda name: f"{name} ({counts[name]:,})",
            placeholder="모든 품종", key=f"{KEY}breeds", on_change=reset_page, select_all=False, **KEEP,
        )  # fmt: skip

        # 입양 매칭으로 이어 가기 (예전에는 검색 조건과 결과 사이에 따로 있어서 결과를 아래로 밀었음)
        if survey is None:
            st.caption("입양 매칭 질문에 답하면 나와 잘 맞는 순으로도 볼 수 있어요.")
        with st.container(horizontal=True, gap="small"):
            st.button("조건 초기화", on_click=reset_filters, type="tertiary", icon=":material/restart_alt:")
            if st.button(
                "이 조건으로 입양 매칭 하기", icon=":material/volunteer_activism:",
                help="고른 조건(지역·크기·나이·성별·품종)을 입양 매칭으로 가져가요. 여기서는 거리를 점수에 넣지 않아요.",
            ):  # fmt: skip
                st.session_state[f"{KEY}go_match"] = True

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


page_header("보호견 둘러보기")

inject_card_css()
data = load_data_or_stop()
st.caption(f"전체 {len(data.dogs):,}마리 · {format_updated(data.fetched_at)}")

# 입양 매칭 설문을 했다면 '나와 잘 맞는 순' 정렬과 적합도 점수를 함께 보여줍니다.
survey = st.session_state.get(S.MATCH_SURVEY)
conditions = filter_controls(data.dogs, survey)
if st.session_state.pop(f"{KEY}go_match", False):
    carry_to_match(conditions)
    st.switch_page("views/match.py")
found = B.filter_dogs(data.dogs, conditions)

# 고른 조건 요약: 검색 조건을 접어 둬도 무엇으로 걸렀는지 보이게
chosen = chosen_labels(conditions)
if chosen:
    with st.container(horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(chips_markdown(chosen), width="content")
        st.button("초기화", key=f"{KEY}reset_chips", on_click=reset_filters, type="tertiary",
                  icon=":material/close:", help="고른 조건을 모두 지워요.")  # fmt: skip

sort_options = [o for o in B.SORT_LABELS if survey is not None or o != B.FIT]
if st.session_state.get(f"{KEY}order") not in sort_options:
    st.session_state[f"{KEY}order"] = B.RECENT

head, sort_col = st.columns([3, 1], vertical_alignment="bottom")
head.header(f"조건에 맞는 아이 {len(found):,}마리", anchor=False)
order = sort_col.selectbox(
    "정렬", sort_options, format_func=B.SORT_LABELS.get, key=f"{KEY}order", on_change=reset_page,
    label_visibility="collapsed", **KEEP,
)  # fmt: skip

if survey is not None and order != B.FIT:
    st.caption("입양 매칭 답변으로 적합도를 계산했어요. 정렬을 '나와 잘 맞는 순'으로 바꿔 보세요.")

# 가까운 순: 기준 위치에서 각 아이의 보호소까지 거리 (카드에도 거리를 보여줌)
locator = ShelterLocator(data.shelters)
distances: dict[str, float | None] = {}
if order == B.NEAREST:
    origin, basis = nearest_origin(conditions)
    if origin is None:
        st.info(basis + " 지금은 최근 등록순이에요.", icon=":material/my_location:")
    else:
        st.caption(f":material/near_me: {basis} 기준으로 가까운 보호소의 아이부터 보여드려요.")
        for dog in found:
            pos = locator.locate(dog)
            distances[str(dog.get("desertionNo"))] = haversine_km(origin, pos) if pos else None

if not found:
    st.info("조건에 맞는 아이가 없어요. 조건을 줄이거나 초기화해 보세요.")
    st.stop()

fits = B.fit_results(found, survey) if survey is not None else {}


def fit_badge(dog: dict) -> str | None:
    result = fits.get(str(dog.get("desertionNo")))
    return score_badge(f"적합도 {result.score}점") if result else None


def fit_detail(dog: dict) -> dict:
    result = fits.get(str(dog.get("desertionNo")))
    if result is None:
        return {}
    return {"score": result.score, "reasons": result.reasons, "cautions": result.cautions}


limit = min(st.session_state.get(f"{KEY}limit", PAGE_SIZE), len(found))
render_dog_cards(
    B.sort_dogs(found, order, fits=fits, distances=distances)[:limit], locator, key_prefix="b",
    badge=fit_badge, detail_kwargs=fit_detail,
    distance_of=(lambda dog: distances.get(str(dog.get("desertionNo")))) if distances else None,
)  # fmt: skip

if limit < len(found):
    st.caption(f"{limit:,} / {len(found):,}마리를 보고 있어요.")
    st.button("더 보기", on_click=show_more, width="stretch")
