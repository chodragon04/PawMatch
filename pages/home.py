import streamlit as st

from pawmatch.api import ApiError, fetch_abandoned_dogs
from pawmatch.config import API_KEY_ENV, get_api_key


@st.cache_data(ttl=3600, show_spinner=False)
def load_preview(api_key: str) -> tuple[list[dict], int]:
    return fetch_abandoned_dogs(api_key, state="protect", rows=8)


st.title("🐾 PawMatch")
st.subheader("사진과 생활 환경으로 찾는 유기견 입양 매칭")

st.write(
    "보호소에 있는 유기견을 사진이나 생활 환경을 기준으로 찾아볼 수 있는 웹서비스입니다. "
    "국가동물보호정보시스템의 구조동물 공공데이터를 활용합니다."
)

st.markdown(
    """
- **보호견 둘러보기**: 지역, 크기 등 조건으로 검색하고 공고 마감이 가까운 아이부터 확인
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

st.divider()

try:
    with st.spinner("보호 중인 아이들을 불러오는 중..."):
        dogs, total = load_preview(api_key)
except ApiError as exc:
    st.error(f"공공데이터를 불러오지 못했습니다.\n\n{exc}")
    st.stop()

st.metric("지금 전국 보호소에서 가족을 기다리는 아이들", f"{total:,}마리")

cols = st.columns(4)
for i, dog in enumerate(dogs):
    with cols[i % 4]:
        if dog.get("popfile1"):
            st.image(dog["popfile1"], width="stretch")
        st.markdown(f"**{dog.get('kindFullNm') or dog.get('kindNm') or '품종 미상'}**")
        st.caption(
            f"{dog.get('age', '')} · {dog.get('careNm', '')}\n\n"
            f"공고 마감 {dog.get('noticeEdt', '-')}"
        )
