"""찜하기: 찜한 아이 목록을 사용자의 브라우저(localStorage)에만 저장합니다. 서버에는 저장하지 않습니다.

- 카드 사진 왼쪽 아래의 하트 버튼은 브라우저에서 바로 localStorage를 바꿉니다. (서버를 거치지 않아 빠름)
- '찜' 화면은 streamlit_js_eval로 localStorage 값을 읽어서 목록을 보여줍니다.
"""

from __future__ import annotations

import html
import json
from urllib.parse import quote

STORAGE_KEY = "pawmatch_favorites"
MAX_FAVORITES = 200  # 너무 많이 쌓이지 않게 최근 찜한 순으로 이만큼만 둡니다

# 찜 화면에서 목록을 읽는 식. 아직 아무것도 없으면 '[]'을 돌려줘서 '아직 못 읽음(None)'과 구분합니다.
READ_JS = f"localStorage.getItem('{STORAGE_KEY}') || '[]'"

# 하트 모양. st.html은 <svg>를 지우므로, CSS 마스크(data URI 이미지)로 그려서 색만 바꿉니다.
_HEART_PATH = (
    "M12 20.5s-7.5-4.6-9.3-9.2C1.5 8 3.6 4.5 7.1 4.5c2 0 3.6 1.1 4.9 2.9 1.3-1.8 2.9-2.9 4.9-2.9 "
    "3.5 0 5.6 3.5 4.4 6.8-1.8 4.6-9.3 9.2-9.3 9.2z"
)


def _heart_mask(filled: bool) -> str:
    paint = "fill='black'" if filled else "fill='none' stroke='black' stroke-width='2'"
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path {paint} d='{_HEART_PATH}'/></svg>"
    return 'url("data:image/svg+xml,' + quote(svg) + '")'


FAVORITE_CSS = """
<style>
.pm-fav { position: absolute; left: 0.5rem; bottom: 0.5rem; z-index: 2; width: 2.3rem; height: 2.3rem;
          padding: 0; border: none; border-radius: 50%; background: rgba(255, 255, 255, 0.92);
          box-shadow: 0 1px 4px rgba(0, 0, 0, 0.18); display: flex; align-items: center; justify-content: center;
          cursor: pointer; -webkit-tap-highlight-color: transparent; }
.pm-fav::before { content: ""; width: 1.35rem; height: 1.35rem; background: #9C8B82;
                  -webkit-mask: __OUTLINE__ center / contain no-repeat; mask: __OUTLINE__ center / contain no-repeat; }
.pm-fav.pm-on::before { background: #FF8A3D;
                        -webkit-mask: __FILLED__ center / contain no-repeat; mask: __FILLED__ center / contain no-repeat; }
.pm-fav:active { transform: scale(0.88); }
</style>
""".replace("__OUTLINE__", _heart_mask(False)).replace("__FILLED__", _heart_mask(True))

# 하트를 누르면 localStorage를 바꾸고, 화면에 있는 같은 아이의 하트를 모두 같이 바꿉니다. (한 번만 등록)
FAVORITE_JS = """
<script>
(function () {
  if (window.__pmFav) return;
  window.__pmFav = true;
  var KEY = __KEY__, MAX = __MAX__;
  function load() {
    try { var v = JSON.parse(localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v.map(String) : []; }
    catch (e) { return []; }
  }
  function paint() {
    var ids = load();
    document.querySelectorAll(".pm-fav").forEach(function (b) {
      var on = ids.indexOf(b.dataset.pmFav) >= 0;
      b.classList.toggle("pm-on", on);
      b.setAttribute("aria-pressed", on ? "true" : "false");
      b.setAttribute("aria-label", on ? "찜 취소" : "찜하기");
    });
  }
  window.__pmFavPaint = paint;
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest(".pm-fav");
    if (!b) return;
    e.preventDefault();
    e.stopPropagation();
    var ids = load(), id = b.dataset.pmFav, at = ids.indexOf(id);
    if (at >= 0) { ids.splice(at, 1); } else { ids.unshift(id); }
    try { localStorage.setItem(KEY, JSON.stringify(ids.slice(0, MAX))); } catch (err) {}
    paint();
  }, true);
  window.addEventListener("storage", function (e) { if (e.key === KEY) paint(); });
  paint();
})();
</script>
""".replace("__KEY__", json.dumps(STORAGE_KEY)).replace("__MAX__", str(MAX_FAVORITES))

# 카드가 새로 그려질 때 그 카드의 하트 상태를 맞춥니다.
PAINT_JS = "<script>window.__pmFavPaint && window.__pmFavPaint();</script>"


def heart_button_html(dog_id: str) -> str:
    """카드 사진 위에 올리는 하트 버튼."""
    did = html.escape(str(dog_id), quote=True)
    return f'<button type="button" class="pm-fav" data-pm-fav="{did}" aria-label="찜하기" aria-pressed="false"></button>'


def parse_favorites(raw: str | None) -> list[str]:
    """localStorage에서 읽은 문자열 → 찜한 아이 번호 목록 (최근 찜한 순, 중복 없음). 망가진 값이면 빈 목록."""
    try:
        values = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    seen: dict[str, None] = {}
    for value in values:
        if isinstance(value, (str, int)) and str(value).strip():
            seen.setdefault(str(value).strip(), None)
    return list(seen)[:MAX_FAVORITES]
