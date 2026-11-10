from dataclasses import replace

import streamlit as st

from pawmatch import browse as B
from pawmatch import matching as M
from pawmatch import state as S
from pawmatch import traits as T
from pawmatch.detail import detail_button
from pawmatch.display import score_badge
from pawmatch.geo import ShelterLocator, sort_by_distance
from pawmatch.location import pick_origin
from pawmatch.ui import inject_card_css, load_data_or_stop, page_header, render_card

PAGE_SIZE = 12  # 한 번에 보여줄 추천 수
MAX_RESULTS = 60  # '더 보기'로 볼 수 있는 최대 추천 수
COLUMNS = 3
MAX_REASONS, MAX_CAUTIONS = 3, 2

DISTANCE_OPTIONS = {"상관없음": None, "10km 이내": 10.0, "30km 이내": 30.0, "50km 이내": 50.0, "100km 이내": 100.0}
SEX_LABELS = {"M": "수컷", "F": "암컷"}
K = S.match_key  # 입력칸 key: 다른 화면에 갔다 와도 값이 남도록 key와 persist_state를 줍니다
PREF_KEYS = [K("sizes"), K("ages"), K("sex"), K("breeds")]


def survey_form(max_km: float | None, breeds: list[tuple[str, int]]) -> M.Survey | None:
    """설문을 보여주고, 제출하면 응답을 돌려줍니다."""
    keep = {"persist_state": S.PERSIST}
    with st.form("match_survey_form"):
        st.markdown("##### 2. 생활 환경")
        home = st.radio(
            "어디에 살고 계신가요?", list(M.HOME_LABELS), format_func=M.HOME_LABELS.get, horizontal=True,
            key=K("home"), **keep,
        )  # fmt: skip
        walk = st.radio(
            "하루에 산책을 얼마나 해줄 수 있나요?", list(M.WALK_LABELS), format_func=M.WALK_LABELS.get, index=1,
            horizontal=True, key=K("walk"), **keep,
        )  # fmt: skip
        away = st.radio(
            "평일에 집을 비우는 시간은 얼마나 되나요?", list(M.AWAY_LABELS), format_func=M.AWAY_LABELS.get, index=1,
            horizontal=True, key=K("away"), **keep,
        )  # fmt: skip
        first_dog = st.radio(
            "반려견을 키워 본 적이 있나요?", [True, False], horizontal=True,
            format_func=lambda first: "처음이에요" if first else "키워 본 적 있어요", key=K("first"), **keep,
        )  # fmt: skip
        st.write("함께 사는 가족")
        has_kids = st.checkbox("어린 아이가 있어요", key=K("kids"), **keep)
        has_pets = st.checkbox("다른 반려동물이 있어요", key=K("pets"), **keep)

        health_ok = st.checkbox("치료나 보살핌이 더 필요한 아이도 괜찮아요", key=K("health"), **keep)

        # 원하는 조건으로 직접 찾는 건 '보호견 둘러보기'의 역할이라, 여기서는 접어 두는 보조 항목입니다.
        # 고른 조건이 있으면(둘러보기에서 가져온 경우 포함) 펼쳐서 보여줍니다.
        has_prefs = any(st.session_state.get(k) for k in PREF_KEYS)
        with st.expander("3. 원하는 아이가 따로 있다면 (선택)", expanded=has_prefs):
            c1, c2 = st.columns(2)
            pref_sizes = c1.pills(
                "크기", list(T.SIZE_LABELS), selection_mode="multi", format_func=T.SIZE_LABELS.get,
                key=K("sizes"), **keep,
            )  # fmt: skip
            pref_ages = c2.pills(
                "나이", list(T.AGE_LABELS), selection_mode="multi", format_func=T.AGE_LABELS.get,
                key=K("ages"), **keep,
            )  # fmt: skip
            pref_sex = st.pills("성별", list(SEX_LABELS), format_func=SEX_LABELS.get, key=K("sex"), **keep)
            counts = dict(breeds)
            chosen_breeds = st.multiselect(
                "품종", [name for name, _ in breeds], format_func=lambda name: f"{name} ({counts.get(name, 0):,})",
                placeholder="모든 품종 (여러 개 고를 수 있어요)",
                help="품종을 고르면 그 품종의 아이만 추천해요. 괄호 안은 지금 보호 중인 마릿수예요.",
                key=K("breeds"), select_all=False, **keep,
            )  # fmt: skip
            st.caption("안 고르면 상관없음 · 여러 개를 고르면 하나만 맞아도 돼요")

        if not st.form_submit_button("나와 잘 맞는 아이 찾기", icon=":material/pets:", type="primary", width="stretch"):
            return None
    return M.Survey(
        home=home, walk=walk, first_dog=first_dog, has_kids=has_kids, has_pets=has_pets, away=away,
        max_km=max_km, pref_sizes=tuple(pref_sizes or ()), pref_ages=tuple(pref_ages or ()),
        pref_sex=pref_sex or M.ANY, health_ok=health_ok, breeds=tuple(chosen_breeds),
    )  # fmt: skip


def render_result(result: M.MatchResult, index: int, locator: ShelterLocator) -> None:
    with st.container(border=True):
        render_card(result.dog, distance_km=result.distance_km, key_prefix=f"match{index}")
        st.markdown(score_badge(f"적합도 {result.score}점"))
        lines = [f"👍 {r}" for r in result.reasons[:MAX_REASONS]]
        lines += [f"⚠️ {c}" for c in result.cautions[:MAX_CAUTIONS]]
        if lines:
            st.caption("\n\n".join(lines))
        detail_button(
            result.dog, locator, key=f"detail_{index}_{result.dog.get('desertionNo')}",
            distance_km=result.distance_km, score=result.score, reasons=result.reasons, cautions=result.cautions,
        )  # fmt: skip


def show_more() -> None:
    st.session_state.match_limit = st.session_state.get("match_limit", PAGE_SIZE) + PAGE_SIZE


page_header("입양 매칭")
st.write("생활 환경을 알려주면 잘 맞는 아이와 **그 이유**를 알려드려요.")

inject_card_css()
data = load_data_or_stop()

notice = st.session_state.pop(S.MATCH_NOTICE, None)
if notice:
    st.success(notice, icon="🐶")

st.markdown("##### 1. 어디에서 찾을까요?")
origin = pick_origin(S.MATCH)
distance_label = st.selectbox(
    "보호소까지 거리", list(DISTANCE_OPTIONS), index=0, disabled=origin is None, key=K("distance"),
    persist_state=S.PERSIST,
)  # fmt: skip
max_km = DISTANCE_OPTIONS[distance_label] if origin is not None else None

submitted = survey_form(max_km, M.breed_options(data.dogs))
if submitted is not None:
    st.session_state[S.MATCH_SURVEY] = submitted
    st.session_state.match_limit = PAGE_SIZE

survey: M.Survey | None = st.session_state.get(S.MATCH_SURVEY)
if survey is None:
    st.stop()

# 위치나 거리 조건이 바뀌면 다시 제출하지 않아도 바로 반영합니다.
survey = replace(survey, max_km=max_km)
locator = ShelterLocator(data.shelters)
if origin is not None:
    ranked = sort_by_distance(data.dogs, locator, origin)
else:
    ranked = [(dog, None) for dog in data.dogs]
results = M.rank_dogs(ranked, survey, limit=MAX_RESULTS)

st.divider()
if not results:
    hint = "보호소까지 거리를 늘리거나 품종을 더 골라 보세요." if survey.breeds else "보호소까지 거리를 늘려 보세요."
    st.warning(f"조건에 맞는 아이가 없어요. {hint}")
    st.stop()

limit = min(st.session_state.get("match_limit", PAGE_SIZE), len(results))
st.subheader(f"나와 잘 맞는 아이 {limit}마리")
if survey.breeds:
    st.caption("품종: " + ", ".join(survey.breeds))
st.caption(
    "점수는 공공데이터로 계산한 참고용이에요. 성격과 건강은 꼭 보호소에 물어봐 주세요."
    + ("" if origin is not None else " 위치를 정하면 거리 점수도 더해져요.")
)

shown = results[:limit]
for start in range(0, len(shown), COLUMNS):
    cols = st.columns(COLUMNS)
    for col, (i, result) in zip(cols, enumerate(shown[start : start + COLUMNS], start)):
        with col:
            render_result(result, i, locator)

if limit < len(results):
    st.button("추천 더 보기", on_click=show_more, width="stretch")

with st.container(border=True):
    st.markdown("**보호견 둘러보기**에서 조건을 좁혀 가며 **나와 잘 맞는 순**으로 볼 수도 있어요.")
    if st.button("둘러보기에서 나와 잘 맞는 순으로 보기", icon=":material/pets:"):
        st.session_state[S.BROWSE_ORDER] = B.FIT
        st.session_state.pop(S.BROWSE_LIMIT, None)  # 둘러보기는 처음 개수부터
        st.switch_page("views/browse.py")

with st.expander("점수는 이렇게 계산해요"):
    st.markdown(
        "\n".join(
            [
                "| 항목 | 비중 | 무엇을 보나요 |",
                "|---|---|---|",
                "| 크기 | 25 | 주거 형태와 체중(어린 강아지는 품종으로 다 자란 크기 추정) |",
                "| 활동량 | 20 | 산책 시간과 나이·품종·특징 메모로 추정한 활동량 |",
                "| 성격 | 20 | 특징 메모의 '온순', '사람 좋아함', '겁', '입질' 등과 반려 경험·가족 구성 |",
                "| 돌봄 시간 | 15 | 집을 비우는 시간과 나이 (어린 강아지는 오래 혼자 두기 어려워요) |",
                "| 거리 | 15 | 기준 위치에서 보호소까지 거리 |",
                "| 선호 | 5 | 원하는 크기·나이(여러 개 가능)·성별, 치료가 필요한 아이 괜찮은지 |",
            ]
        )
    )
    st.caption(
        "정보가 없는 항목(예: 특징 메모에 성격 이야기가 없음)은 감점하지 않고 중간 점수로 계산해요. "
        "품종과 보호소까지 거리는 점수가 아니라 조건이라서, 고르면 그에 맞는 아이만 추천해요. "
        "자세한 기준은 저장소의 pawmatch/matching.py와 docs/data-analysis.md에 있어요."
    )
