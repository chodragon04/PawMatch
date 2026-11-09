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
