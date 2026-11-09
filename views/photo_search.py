import time

import streamlit as st

from pawmatch import state as S
from pawmatch.detail import render_dog_cards
from pawmatch.display import format_updated
from pawmatch.geo import REGION_CENTERS, ShelterLocator, address_in_area
from pawmatch.image_search import ClipEmbedder, PhotoIndex, load_image, read_local_index, read_remote_index
from pawmatch.ui import inject_card_css, load_data_or_stop

TOP_K = 24
COLUMNS = 4
WHOLE_COUNTRY = "전국"
LOW_SIMILARITY = 0.7  # 가장 닮은 아이도 이보다 낮으면 안내 (강아지가 아닌 사진은 실측 0.55~0.60, 다른 강아지끼리 중앙값 0.75)
UPLOAD_TYPES = ["jpg", "jpeg", "png", "webp"]
# 카메라는 '카메라 켜기'를 눌렀을 때만 켜고, 켠 뒤 이 시간 동안은 이 화면에 다시 와도 바로 켜서
# 카메라 권한을 매번 다시 묻지 않게 합니다. (이 브라우저 탭의 세션에만 기억)
CAMERA_TTL_S = 30 * 60
CAMERA_ON_KEY = "photo_camera_on_at"


def camera_is_on() -> bool:
    started = st.session_state.get(CAMERA_ON_KEY)
    return started is not None and time.time() - started <= CAMERA_TTL_S


def turn_camera_on() -> None:
    st.session_state[CAMERA_ON_KEY] = time.time()


def turn_camera_off() -> None:
    st.session_state.pop(CAMERA_ON_KEY, None)
    st.session_state.pop("photo_camera", None)


@st.cache_resource(show_spinner=False)
def get_embedder() -> ClipEmbedder:
    """CLIP 모델은 서버에서 한 번만 불러와 모든 사용자가 같이 씁니다."""
    return ClipEmbedder()


@st.cache_resource(ttl=1800, show_spinner=False)
def get_index() -> PhotoIndex | None:
    """보호견 사진 임베딩: 로컬 파일 → data 브랜치 순서로 찾고, 30분마다 다시 읽습니다."""
    return read_local_index() or read_remote_index()


@st.cache_data(max_entries=32, show_spinner=False)
def embed_photo(data: bytes):
    """올린 사진의 임베딩. 같은 사진이면 다시 계산하지 않습니다. (사진은 메모리에만 잠깐 있고 저장하지 않음)"""
    return get_embedder()([load_image(data)])[0]


st.title("📷 사진으로 찾기")
st.write(
    "강아지 사진을 올리면, 지금 보호소에 있는 아이들 중 **생김새가 비슷한 아이**를 찾아드려요. "
    "잃어버린 반려견을 찾을 때나, 마음에 드는 생김새의 아이를 찾을 때 써 보세요."
)
st.caption("올린 사진은 비슷한 아이를 찾는 데에만 쓰고 저장하지 않아요.")

inject_card_css()
data = load_data_or_stop()
index = get_index()
if index is None or not len(index):
    st.info("보호견 사진을 분석한 데이터를 준비하고 있어요. 잠시 뒤 다시 와 주세요.")
    st.stop()

with st.container(border=True):
    upload_tab, camera_tab = st.tabs(["🖼️ 사진 올리기", "📸 카메라로 찍기"])
    uploaded = upload_tab.file_uploader(
        "강아지 사진", type=UPLOAD_TYPES, key="photo_upload", label_visibility="collapsed",
        help="강아지 얼굴과 몸이 잘 보이는 사진일수록 잘 찾아요.",
    )  # fmt: skip
    taken = None
    with camera_tab:
        if camera_is_on():
            taken = st.camera_input("강아지를 찍어 주세요", key="photo_camera")
            st.button("카메라 끄기", on_click=turn_camera_off, type="tertiary", icon=":material/videocam_off:")
        else:
            st.caption("카메라는 아래 버튼을 눌렀을 때만 켜요. 한 번 켜면 30분 동안은 이 화면에 다시 와도 바로 켜져요.")
            st.button("카메라 켜기", on_click=turn_camera_on, icon=":material/photo_camera:")
    sido = st.selectbox(
        "어디에서 찾을까요?", [WHOLE_COUNTRY, *REGION_CENTERS], key="photo_sido", persist_state=S.PERSIST,
        help="보호소 주소 기준이에요.",
    )  # fmt: skip

photo = uploaded or taken
if photo is None:
    st.caption("사진을 올리거나 찍으면 바로 찾기 시작해요.")
    st.stop()

try:
    with st.spinner("사진을 분석하는 중이에요... (처음 한 번은 분석 모델을 준비하느라 1분 정도 걸릴 수 있어요)"):
        query = embed_photo(photo.getvalue())
except Exception as exc:  # 깨진 사진, 모델 내려받기 실패 등
    st.error(f"사진을 분석하지 못했어요. 다른 사진으로 다시 시도해 주세요.\n\n({exc})")
    st.stop()

by_id = {str(dog.get("desertionNo")): dog for dog in data.dogs}
allowed = {
    dog_id for dog_id, dog in by_id.items()
    if sido == WHOLE_COUNTRY or address_in_area(dog.get("careAddr"), sido)
}  # fmt: skip
searchable = allowed & index.dog_ids()
results = index.search(query, top_k=TOP_K, allowed=searchable)

preview, summary = st.columns([1, 3], vertical_alignment="center")
preview.image(photo, caption="올린 사진", width="stretch")
with summary:
    where = "전국" if sido == WHOLE_COUNTRY else sido
    st.subheader(f"생김새가 비슷한 아이 {len(results)}마리")
    st.caption(
        f"{where}에서 사진 분석이 끝난 {len(searchable):,}마리 중에서 찾았어요. "
        f"(사진 분석 {format_updated(index.created_at)}"
        + (f", 아직 분석 전인 {len(allowed) - len(searchable):,}마리 제외)" if len(allowed) > len(searchable) else ")")
    )
    if results and results[0][1] < LOW_SIMILARITY:
        st.warning("많이 닮은 아이를 찾지 못했어요. 강아지가 크게 잘 보이는 사진으로 다시 시도해 보세요.")
    st.caption("닮은 정도는 사진 속 생김새(털색, 얼굴, 몸집 등)가 얼마나 비슷한지예요. 배경이나 찍은 각도도 영향을 줄 수 있어요.")

if not results:
    st.info("조건에 맞는 아이가 없어요. 지역을 넓혀 보세요.")
    st.stop()

# 카드에는 가장 닮은 사진을 먼저 보여줍니다. (popfile0으로 넣으면 사진 목록 맨 앞에 옴)
scores = {dog_id: score for dog_id, score, _ in results}
cards = [{**by_id[dog_id], "popfile0": url} for dog_id, _, url in results]
render_dog_cards(
    cards, ShelterLocator(data.shelters), columns=COLUMNS, key_prefix="p",
    badge=lambda dog: f":blue-badge[닮은 정도 {round(scores[str(dog.get('desertionNo'))] * 100)}%]",
)  # fmt: skip
