import streamlit as st
from streamlit_js_eval import streamlit_js_eval

from pawmatch import favorites as F
from pawmatch.detail import render_dog_cards
from pawmatch.geo import ShelterLocator
from pawmatch.ui import inject_card_css, load_data_or_stop, page_header

COLUMNS = 4
VISIT_KEY = "pm_page_visit"  # app.py가 화면을 옮길 때마다 1씩 올림 → 들어올 때마다 찜 목록을 새로 읽음

page_header("찜한 아이")
inject_card_css()
data = load_data_or_stop()

# 목록을 읽는 보이지 않는 칸이 화면에 빈 자리를 만들지 않게 높이를 0으로 (동작에는 영향 없음)
st.html("""<style>
[data-testid="stElementContainer"]:has(iframe[title="streamlit_js_eval.streamlit_js_eval"]) {
  height: 0 !important; min-height: 0 !important; overflow: hidden; margin: 0 !important; }
</style>""")
raw = streamlit_js_eval(js_expressions=F.READ_JS, key=f"favorites_read_{st.session_state.get(VISIT_KEY, 0)}")
if raw is None:  # 브라우저에서 아직 값을 못 받음 (곧 다시 그려짐)
    st.caption("찜 목록을 불러오는 중...")
    st.stop()

ids = F.parse_favorites(raw)
if not ids:
    st.info("아직 찜한 아이가 없어요. 사진 왼쪽 아래 ♡를 눌러 보세요.", icon=":material/favorite:")
    st.stop()

by_id = {str(dog.get("desertionNo")): dog for dog in data.dogs}
dogs = [by_id[dog_id] for dog_id in ids if dog_id in by_id]
gone = len(ids) - len(dogs)
st.caption(
    f"{len(dogs)}마리 · 이 기기의 브라우저에만 저장돼요"
    + (f" · 입양됐거나 공고가 끝난 {gone}마리는 보이지 않아요" if gone else "")
)
render_dog_cards(dogs, ShelterLocator(data.shelters), columns=COLUMNS, key_prefix="f")
