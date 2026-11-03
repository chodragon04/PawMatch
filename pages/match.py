from dataclasses import replace

import streamlit as st

from pawmatch import matching as M
from pawmatch import traits as T
from pawmatch.geo import ShelterLocator, sort_by_distance
from pawmatch.location import pick_origin
from pawmatch.ui import inject_card_css, load_data_or_stop, render_card

PAGE_SIZE = 12  # 한 번에 보여줄 추천 수
MAX_RESULTS = 60  # '더 보기'로 볼 수 있는 최대 추천 수
COLUMNS = 3
MAX_REASONS, MAX_CAUTIONS = 3, 2

DISTANCE_OPTIONS = {"상관없음": None, "10km 이내": 10.0, "30km 이내": 30.0, "50km 이내": 50.0, "100km 이내": 100.0}
SIZE_OPTIONS = {M.ANY: "상관없음", **T.SIZE_LABELS}
AGE_OPTIONS = {M.ANY: "상관없음", **T.AGE_LABELS}


def survey_form(max_km: float | None) -> M.Survey | None:
    """설문을 보여주고, 제출하면 응답을 돌려줍니다."""
    with st.form("match_survey_form"):
        st.markdown("##### 2. 생활 환경")
        home = st.radio("어디에 살고 계신가요?", list(M.HOME_LABELS), format_func=M.HOME_LABELS.get, horizontal=True)
        walk = st.radio(
            "하루에 산책을 얼마나 해줄 수 있나요?", list(M.WALK_LABELS), format_func=M.WALK_LABELS.get, index=1,
            horizontal=True,
        )  # fmt: skip
        away = st.radio(
            "평일에 집을 비우는 시간은 얼마나 되나요?", list(M.AWAY_LABELS), format_func=M.AWAY_LABELS.get, index=1,
            horizontal=True,
        )  # fmt: skip
        first_dog = st.radio(
            "반려견을 키워 본 적이 있나요?", [True, False], horizontal=True,
            format_func=lambda first: "처음이에요" if first else "키워 본 적 있어요",
        )  # fmt: skip
        st.write("함께 사는 가족")
        has_kids = st.checkbox("어린 아이가 있어요")
        has_pets = st.checkbox("다른 반려동물이 있어요")

        st.markdown("##### 3. 원하는 아이 (선택)")
        c1, c2, c3 = st.columns(3)
        pref_size = c1.selectbox("크기", list(SIZE_OPTIONS), format_func=SIZE_OPTIONS.get)
        pref_age = c2.selectbox("나이", list(AGE_OPTIONS), format_func=AGE_OPTIONS.get)
        pref_sex = c3.selectbox("성별", list(M.SEX_PREF_LABELS), format_func=M.SEX_PREF_LABELS.get)
        health_ok = st.checkbox("치료나 보살핌이 더 필요한 아이도 괜찮아요")

        if not st.form_submit_button("🐾 나와 잘 맞는 아이 찾기", type="primary", width="stretch"):
            return None
    return M.Survey(
        home=home, walk=walk, first_dog=first_dog, has_kids=has_kids, has_pets=has_pets, away=away,
        max_km=max_km, pref_size=pref_size, pref_age=pref_age, pref_sex=pref_sex, health_ok=health_ok,
    )  # fmt: skip


def render_result(result: M.MatchResult, index: int) -> None:
    render_card(result.dog, distance_km=result.distance_km, key_prefix=f"match{index}")
    st.markdown(f":violet-badge[적합도 {result.score}점]")
    lines = [f"👍 {r}" for r in result.reasons[:MAX_REASONS]]
    lines += [f"⚠️ {c}" for c in result.cautions[:MAX_CAUTIONS]]
    if lines:
        st.caption("\n\n".join(lines))


def show_more() -> None:
    st.session_state.match_limit = st.session_state.get("match_limit", PAGE_SIZE) + PAGE_SIZE


st.title("🏠 입양 매칭")
st.write(
    "생활 환경에 대한 몇 가지 질문에 답하면, 보호소 정보를 바탕으로 잘 맞을 것 같은 아이를 추천해 드려요. "
    "점수는 보호소가 적은 체중·나이·특징 메모로 계산한 **참고용**이니, 마음에 드는 아이가 있다면 "
    "꼭 보호소에 성격과 건강 상태를 문의해 주세요."
)

inject_card_css()
data = load_data_or_stop()

st.markdown("##### 1. 어디에서 찾을까요?")
origin = pick_origin("match")
distance_label = st.selectbox("보호소까지 거리", list(DISTANCE_OPTIONS), index=0, disabled=origin is None)
max_km = DISTANCE_OPTIONS[distance_label] if origin is not None else None

submitted = survey_form(max_km)
if submitted is not None:
    st.session_state.match_survey = submitted
    st.session_state.match_limit = PAGE_SIZE

survey: M.Survey | None = st.session_state.get("match_survey")
if survey is None:
    st.stop()

# 위치나 거리 조건이 바뀌면 다시 제출하지 않아도 바로 반영합니다.
survey = replace(survey, max_km=max_km)
if origin is not None:
    ranked = sort_by_distance(data.dogs, ShelterLocator(data.shelters), origin)
else:
    ranked = [(dog, None) for dog in data.dogs]
results = M.rank_dogs(ranked, survey, limit=MAX_RESULTS)

st.divider()
if not results:
    st.warning("조건에 맞는 아이가 없어요. 보호소까지 거리를 늘려 보세요.")
    st.stop()

limit = min(st.session_state.get("match_limit", PAGE_SIZE), len(results))
st.subheader(f"나와 잘 맞을 것 같은 아이들 (상위 {limit}마리)")
if origin is None:
    st.caption("위치를 정하면 가까운 보호소의 아이에게 거리 점수가 더해져요.")

shown = results[:limit]
for start in range(0, len(shown), COLUMNS):
    cols = st.columns(COLUMNS)
    for col, (i, result) in zip(cols, enumerate(shown[start : start + COLUMNS], start)):
        with col:
            render_result(result, i)

if limit < len(results):
    st.button("추천 더 보기", on_click=show_more, width="stretch")

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
                "| 선호 | 5 | 원하는 크기·나이·성별, 치료가 필요한 아이 괜찮은지 |",
            ]
        )
    )
    st.caption(
        "정보가 없는 항목(예: 특징 메모에 성격 이야기가 없음)은 감점하지 않고 중간 점수로 계산해요. "
        "자세한 기준은 저장소의 pawmatch/matching.py와 docs/data-analysis.md에 있어요."
    )
