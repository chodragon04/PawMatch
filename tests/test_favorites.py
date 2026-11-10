from pawmatch.favorites import MAX_FAVORITES, heart_button_html, parse_favorites
from pawmatch.ui import carousel_html, photo_html


def test_parse_favorites_keeps_order_and_drops_duplicates():
    assert parse_favorites('["3", "1", "3", 2]') == ["3", "1", "2"]


def test_parse_favorites_handles_broken_values():
    assert parse_favorites(None) == []
    assert parse_favorites("") == []
    assert parse_favorites("not json") == []
    assert parse_favorites('{"a": 1}') == []
    assert parse_favorites('[null, "", " ", {"x": 1}, "7"]') == ["7"]


def test_parse_favorites_is_capped():
    raw = "[" + ",".join(f'"{i}"' for i in range(MAX_FAVORITES + 50)) + "]"
    assert len(parse_favorites(raw)) == MAX_FAVORITES


def test_heart_button_escapes_id():
    button = heart_button_html('1"><script>')
    assert 'data-pm-fav="1&quot;&gt;&lt;script&gt;"' in button
    assert "<script>" not in button


def test_card_photo_has_heart_even_without_photos():
    assert 'data-pm-fav="123"' in photo_html({"desertionNo": "123"}, "x")
    assert 'data-pm-fav="123"' in photo_html({"desertionNo": "123", "popfile1": "https://a/b.jpg"}, "y")
    assert "pm-fav" not in photo_html({}, "z")


def test_detail_carousel_has_heart():
    assert 'data-pm-fav="123"' in carousel_html({"desertionNo": "123", "popfile1": "https://a/b.jpg"}, "d")
    assert 'data-pm-fav="123"' in carousel_html({"desertionNo": "123"}, "e")  # 사진이 없어도 찜은 가능
