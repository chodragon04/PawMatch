import streamlit as st

from pawmatch.config import API_KEY_ENV, get_api_key

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

if get_api_key() is None:
    st.warning(
        f"공공데이터 API 키가 설정되지 않았습니다. `.env` 파일에 `{API_KEY_ENV}` 값을 넣어주세요."
    )
