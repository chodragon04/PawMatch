# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""pawmatch.ui 단위 테스트 (사진 주소 처리, HTML 생성)."""

from pawmatch.ui import PHOTO_FAIL_TITLE, photo_html, photo_urls, shows_cloud_badge


def test_animal_go_kr_photos_use_https():
    dog = {
        "popfile1": "http://openapi.animal.go.kr/openapi/service/rest/fileDownloadSrvc/files/shelter/a.jpg",
        "popfile2": "http://other.example.com/b.jpg",  # 다른 서버는 그대로 둡니다
    }
    assert photo_urls(dog) == [
        "https://openapi.animal.go.kr/openapi/service/rest/fileDownloadSrvc/files/shelter/a.jpg",
        "http://other.example.com/b.jpg",
    ]


def test_photo_urls_ordered_unique_and_http_only():
    dog = {
        "popfile2": "https://img/2.jpg",
        "popfile1": "https://img/1.jpg",
        "popfile10": "https://img/10.jpg",
        "popfile3": "https://img/1.jpg",  # 중복
        "popfile4": "",  # 빈 값
        "popfile5": "javascript:alert(1)",  # http(s)가 아닌 주소
        "popfileX": "https://img/x.jpg",  # 키 형식이 다름
    }
    assert photo_urls(dog) == ["https://img/1.jpg", "https://img/2.jpg", "https://img/10.jpg"]


def test_photo_html_without_photos_shows_failure_message():
    out = photo_html({"popfile1": ""}, "pm-photo-1")
    assert "pm-failed" in out and PHOTO_FAIL_TITLE in out
    assert "<img" not in out and "<script" not in out


def test_photo_html_escapes_values():
    dog = {"popfile1": 'https://img/a.jpg?x="><script>bad()</script>', "kindFullNm": '<b>"믹스"</b>'}
    out = photo_html(dog, "pm-photo-1")
    assert "<script>bad()" not in out
    assert "&lt;b&gt;&quot;믹스&quot;&lt;/b&gt;" in out
    assert 'data-srcs="[&quot;https://img/a.jpg' in out
    assert '"pm-photo-1"' in out  # 스크립트에서 찾을 id


def test_shows_cloud_badge_only_on_streamlit_cloud():
    assert shows_cloud_badge("https://pawmatch-kr.streamlit.app/browse")
    assert shows_cloud_badge("https://pawmatch-kr.streamlit.app/~/+/match")
    assert not shows_cloud_badge("https://pawmatch-kr.streamlit.app/", embedded=True)
    assert not shows_cloud_badge("http://localhost:8501/")
    assert not shows_cloud_badge("https://streamlit.app.example.com/")
    assert not shows_cloud_badge(None)


def test_a11y_script_marks_language_tab_and_korean_labels():
    from pawmatch.ui import a11y_script

    script = a11y_script(2)
    assert "window.__pmNavActive = 2;" in script
    assert 'doc.lang = "ko"' in script and "aria-current" in script
    assert '"Upload": "사진 고르기"' in script and '"Take Photo": "사진 찍기"' in script
    assert "__" + "LABELS__" not in script  # 자리표시가 모두 채워짐


def test_a11y_script_shows_drop_hint_only_on_pc():
    from pawmatch.ui import UPLOAD_LIMIT_TEXT, UPLOAD_LIMIT_TEXT_PC, a11y_script

    script = a11y_script(0)
    assert "(hover: hover) and (pointer: fine)" in script  # 마우스가 있는 기기에서만
    assert UPLOAD_LIMIT_TEXT_PC.startswith("여기로 끌어다 놓아도 돼요") and UPLOAD_LIMIT_TEXT in UPLOAD_LIMIT_TEXT_PC
    assert "__LIMIT" not in script  # 자리표시가 모두 채워짐


def test_carousel_works_with_keyboard():
    from pawmatch.ui import carousel_html

    dog = {"desertionNo": "1", "kindNm": "믹스견", "popfile1": "https://a/1.jpg", "popfile2": "https://a/2.jpg"}
    page = carousel_html(dog, "c1")
    assert page.count('tabindex="0" role="button"') == 2  # 썸네일을 Tab으로 고를 수 있음
    assert 'alt="사진 2 보기"' in page
    assert "ArrowRight" in page and "ArrowLeft" in page
    assert 'data-pm-name="믹스견' in page  # 상세 창 하트도 아이 이름을 읽어 줌


def test_is_phone_by_user_agent():
    from pawmatch.ui import is_phone

    assert is_phone("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)")
    assert is_phone("Mozilla/5.0 (Linux; Android 14; SM-S918N) AppleWebKit/537.36 Mobile Safari/537.36")
    assert not is_phone("Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 Safari/537.36")  # 태블릿
    assert not is_phone("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    assert not is_phone("")  # 모르면 PC로 봄


def test_pc_top_menu_keeps_gap_from_streamlit_toolbar():
    from pawmatch.ui import A11Y_JS, NAV_CLOUD_BADGE_CSS, NAV_TOP_CSS, TOOLBAR_GAP_PX

    # 위쪽 메뉴 오른쪽 여백 = max(본문 여백, Streamlit 버튼 폭 + 고정 간격)
    assert f"--pm-toolbar-gap: {TOOLBAR_GAP_PX}px" in NAV_TOP_CSS
    assert "calc(var(--pm-toolbar-w, 3rem) + var(--pm-toolbar-gap))" in NAV_TOP_CSS
    assert "--pm-toolbar-w" in A11Y_JS  # 화면에서 버튼 폭을 잼
    assert "--pm-toolbar-w: 220px" in NAV_CLOUD_BADGE_CSS  # 배포 사이트: 재기 전 기본 폭
