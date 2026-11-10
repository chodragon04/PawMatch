# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""앱 화면 테스트: 실제 app.py를 Streamlit AppTest로 돌려서, 화면마다 오류 없이 뜨고 주요 동작이 되는지 확인합니다.

브라우저 없이 서버 쪽 코드만 돌리므로 빠르고(몇 초), 네트워크·API 키·이미지 모델 없이 가짜 데이터로 돌아갑니다.
브라우저에서만 도는 부분(하트 버튼 JS, 내 위치, 화면 배치)은 여기서 확인하지 않습니다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import streamlit as st
import streamlit_js_eval
from streamlit.testing.v1 import AppTest

from pawmatch import data as D
from pawmatch import image_search as IS
from pawmatch.location import PICK_REGION

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TIMEOUT = 60  # 첫 실행은 모듈을 불러오느라 몇 초 걸립니다


def dog(no: str, **kw) -> dict:
    base = {
        "desertionNo": no, "kindFullNm": "[개] 믹스견", "kindNm": "믹스견", "age": "2022(년생)", "weight": "5(Kg)",
        "sexCd": "M", "neuterYn": "Y", "colorCd": "흰색", "specialMark": "온순하고 사람을 좋아함",
        "careNm": "수원시 동물보호센터", "careTel": "031-000-0000", "careAddr": "경기도 수원시 영통구 광교호수로 234",
        "noticeSdt": "20261101", "noticeEdt": "20261130", "happenDt": "20261031", "processState": "보호중",
        "popfile1": "https://example.com/1.jpg",
    }  # fmt: skip
    return {**base, **kw}


DOGS = [
    dog("1001"),
    dog("1002", kindFullNm="[개] 진도견", kindNm="진도견", weight="18(Kg)", sexCd="F"),
    dog("1003", kindFullNm="[개] 푸들", kindNm="푸들", age="2026(60일미만)(년생)", weight="1.5(Kg)"),
    dog("2001", careNm="부산 보호소", careAddr="부산광역시 강서구 군라길 1", weight="30(Kg)", noticeEdt="20261102"),
    dog("2002", careNm="부산 보호소", careAddr="부산광역시 강서구 군라길 1", popfile1=""),  # 사진 없음
]
SHELTERS = [
    {"careNm": "수원시 동물보호센터", "careAddr": "경기도 수원시 영통구 광교호수로 234", "lat": 37.28, "lng": 127.06,
     "careTel": "031-000-0000", "weekOprStime": "09:00", "weekOprEtime": "18:00"},
    {"careNm": "부산 보호소", "careAddr": "부산광역시 강서구 군라길 1", "lat": 35.16, "lng": 128.89},
]  # fmt: skip


@pytest.fixture(autouse=True)
def fake_world(monkeypatch):
    """가짜 데이터·사진 임베딩을 넣고, 네트워크를 쓰는 함수를 막습니다."""
    st.cache_data.clear()
    st.cache_resource.clear()
    monkeypatch.setattr(D.STORE, "dataset", D.Dataset(DOGS, SHELTERS, datetime.now(timezone.utc), D.SNAPSHOT))
    vectors = IS.normalize(np.eye(3, IS.DIM, dtype=np.float32))
    index = IS.PhotoIndex(np.array(["1001", "1002", "2001"]), np.array(["u1", "u2", "u3"]), vectors,
                          created_at=datetime.now(timezone.utc))  # fmt: skip
    monkeypatch.setattr(IS, "read_local_index", lambda *a, **k: index)
    monkeypatch.setattr(IS, "read_remote_index", lambda *a, **k: None)
    monkeypatch.setenv("KAKAO_REST_API_KEY", "")
    yield
    st.cache_data.clear()
    st.cache_resource.clear()


def open_page(path: str | None = None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    if path:
        at.switch_page(path).run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def texts(at: AppTest) -> str:
    """화면에 나온 글(마크다운·캡션·제목·안내)을 한 덩어리로."""
    parts = [*at.markdown, *at.caption, *at.subheader, *at.header, *at.title, *at.info, *at.warning, *at.success]
    return "\n".join(str(p.value) for p in parts)


def test_home_shows_count_and_nearby_shelters_by_region():
    at = open_page()
    assert "지금 가족을 기다리는 아이들" in texts(at)
    assert "5마리" in texts(at)

    at.radio(key="home_mode").set_value(PICK_REGION).run()
    at.selectbox(key="home_region").set_value("경기도").run()
    assert not at.exception
    page = texts(at)
    assert "#### 수원시 동물보호센터" in page
    assert page.index("수원시 동물보호센터") < page.index("부산 보호소")  # 경기도 안 보호소가 먼저


def test_browse_filters_by_region():
    at = open_page("views/browse.py")
    assert "조건에 맞는 아이 5마리" in texts(at)

    at.selectbox(key="browse_sido").set_value("부산광역시").run()
    assert not at.exception
    assert "조건에 맞는 아이 2마리" in texts(at)


def test_match_survey_gives_ranked_results():
    at = open_page("views/match.py")
    at.radio(key="match_mode").set_value(PICK_REGION).run()
    submit = next(b for b in at.button if "나와 잘 맞는 아이 찾기" in b.label)
    submit.click().run()
    assert not at.exception
    assert "나와 잘 맞는 아이" in texts(at)
    assert "적합도" in texts(at)


def test_photo_search_page_opens_with_index():
    at = open_page("views/photo_search.py")
    assert "닮은 보호견" in texts(at)
    assert "준비하고 있어요" not in texts(at)  # 가짜 임베딩이 있으니 준비 중 안내가 아님


def test_favorites_page_lists_saved_dogs(monkeypatch):
    # 브라우저의 localStorage 대신 가짜 값을 돌려줍니다. (찜 화면이 이 함수를 불러 씀)
    monkeypatch.setattr(streamlit_js_eval, "streamlit_js_eval", lambda **_: '["1002", "9999"]')
    at = open_page("views/favorites.py")
    page = texts(at)
    assert "1마리" in page
    assert "공고가 끝난 1마리" in page  # 데이터에 없는 9999


def test_favorites_page_when_empty(monkeypatch):
    monkeypatch.setattr(streamlit_js_eval, "streamlit_js_eval", lambda **_: "[]")
    at = open_page("views/favorites.py")
    assert "아직 찜한 아이가 없어요" in texts(at)
