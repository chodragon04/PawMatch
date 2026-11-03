"""PawMatch Streamlit 앱 진입점.

실행: streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="PawMatch", page_icon="🐾", layout="wide")

pages = [
    st.Page("pages/home.py", title="홈", icon="🐾", default=True),
    st.Page("pages/browse.py", title="보호견 둘러보기", icon="🐶"),
    st.Page("pages/match.py", title="입양 매칭", icon="🏠"),
    st.Page("pages/photo_search.py", title="사진으로 찾기", icon="📷"),
]

st.navigation(pages).run()
