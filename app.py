"""PawMatch Streamlit 앱 진입점.

실행: streamlit run app.py

화면 파일은 views/ 폴더에 있습니다. 폴더 이름이 pages/이면 Streamlit이 예전 방식의 자동 페이지 목록으로도
읽어서, 서버가 켜진 직후 /match 같은 주소로 처음 들어오면 메뉴가 파일 이름으로 보이는 문제가 있었습니다.

메뉴는 Streamlit 기본 사이드바 대신 모든 화면 맨 아래에 고정된 아이콘 탭으로 보여줍니다.
(사이드바 메뉴는 모바일에서 왼쪽 위 >> 버튼을 눌러야 보여서 찾기 어려웠고,
위쪽 버튼 줄은 휴대폰에서 칸 안에서 옆으로 밀려 보였습니다)
"""

import sys
from pathlib import Path

import streamlit as st


def drop_stale_modules(package: str = "pawmatch") -> None:
    """서버가 켜진 채로 코드가 바뀌었으면(배포 갱신) 이미 불러온 pawmatch 모듈을 버려서 새 코드로 다시 불러오게 합니다.

    Streamlit은 app.py와 화면 파일은 매번 새로 읽지만, import한 모듈은 접속 중인 사람이 없을 때 파일이 바뀌면
    예전 코드를 그대로 씁니다. 그러면 새 app.py가 예전 함수를 불러서 TypeError가 납니다. (Streamlit Cloud에서 실제로 발생)
    """
    loaded = sys.modules.get(package)
    if loaded is None:
        return
    folder = Path(__file__).resolve().parent / package
    newest = max((p.stat().st_mtime for p in folder.iterdir() if p.is_file()), default=0.0)
    loaded_at = getattr(loaded, "LOADED_AT", None)
    if loaded_at is None or newest > loaded_at:
        for name in [n for n in sys.modules if n == package or n.startswith(package + ".")]:
            del sys.modules[name]


drop_stale_modules()

from pawmatch.ui import render_nav_bar  # drop_stale_modules() 뒤에 불러와야 합니다

st.set_page_config(page_title="PawMatch", page_icon="🐾", layout="wide")

pages = [
    st.Page("views/home.py", title="홈", icon=":material/home:", default=True),
    st.Page("views/browse.py", title="보호견 둘러보기", icon=":material/pets:"),
    st.Page("views/match.py", title="입양 매칭", icon=":material/volunteer_activism:"),
    st.Page("views/photo_search.py", title="사진으로 찾기", icon=":material/photo_camera:"),
    st.Page("views/favorites.py", title="찜한 아이", icon=":material/favorite:"),
]
# 하단 탭에는 짧은 이름을 씁니다.
SHORT_TITLES = {"보호견 둘러보기": "둘러보기", "입양 매칭": "매칭", "사진으로 찾기": "사진 찾기", "찜한 아이": "찜"}

page = st.navigation(pages, position="hidden")
# 다른 화면에서 넘어올 때마다 1씩 올립니다. (찜 화면이 들어올 때마다 브라우저의 찜 목록을 새로 읽도록)
if st.session_state.get("pm_page") != page.url_path:
    st.session_state["pm_page"] = page.url_path
    st.session_state["pm_page_visit"] = st.session_state.get("pm_page_visit", 0) + 1
render_nav_bar(pages, page, short_titles=SHORT_TITLES)
page.run()
