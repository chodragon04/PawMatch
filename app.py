"""PawMatch Streamlit 앱 진입점.

실행: streamlit run app.py

화면 파일은 views/ 폴더에 있습니다. 폴더 이름이 pages/이면 Streamlit이 예전 방식의 자동 페이지 목록으로도
읽어서, 서버가 켜진 직후 /match 같은 주소로 처음 들어오면 메뉴가 파일 이름으로 보이는 문제가 있었습니다.
"""

import streamlit as st

st.set_page_config(page_title="PawMatch", page_icon="🐾", layout="wide")

pages = [
    st.Page("views/home.py", title="홈", icon="🐾", default=True),
    st.Page("views/browse.py", title="보호견 둘러보기", icon="🐶"),
    st.Page("views/match.py", title="입양 매칭", icon="🏠"),
    st.Page("views/photo_search.py", title="사진으로 찾기", icon="📷"),
]

st.navigation(pages).run()
