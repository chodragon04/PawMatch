"""PawMatch Streamlit 앱 진입점.

실행: streamlit run app.py

화면 파일은 views/ 폴더에 있습니다. 폴더 이름이 pages/이면 Streamlit이 예전 방식의 자동 페이지 목록으로도
읽어서, 서버가 켜진 직후 /match 같은 주소로 처음 들어오면 메뉴가 파일 이름으로 보이는 문제가 있었습니다.

메뉴는 Streamlit 기본 사이드바 대신 모든 화면 맨 아래에 고정된 아이콘 탭으로 보여줍니다.
(사이드바 메뉴는 모바일에서 왼쪽 위 >> 버튼을 눌러야 보여서 찾기 어려웠고,
위쪽 버튼 줄은 휴대폰에서 칸 안에서 옆으로 밀려 보였습니다)
"""

import streamlit as st

from pawmatch.ui import render_nav_bar

st.set_page_config(page_title="PawMatch", page_icon="🐾", layout="wide")

pages = [
    st.Page("views/home.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/browse.py", title="보호견 둘러보기", icon=":material/pets:"),
    st.Page("views/match.py", title="입양 매칭", icon=":material/volunteer_activism:"),
    st.Page("views/photo_search.py", title="사진으로 찾기", icon=":material/photo_camera:"),
]
# 하단 탭에는 짧은 이름을 씁니다.
SHORT_TITLES = {"보호견 둘러보기": "둘러보기", "입양 매칭": "매칭", "사진으로 찾기": "사진 찾기"}

page = st.navigation(pages, position="hidden")
render_nav_bar(pages, page, short_titles=SHORT_TITLES)
page.run()
