"""여러 페이지에서 같이 쓰는 화면 구성 요소 (유기견 카드 등)."""

from __future__ import annotations

import html
import json
import re

import streamlit as st

from pawmatch.display import adoption_status, format_age, format_sex

PHOTO_FAIL_TITLE = "사진을 불러오지 못했어요"
PHOTO_FAIL_DETAIL = "보호소에 문의하면 아이의 모습을 확인할 수 있어요"

_POPFILE_RE = re.compile(r"^popfile(\d+)$")

CARD_CSS = """
<style>
.pm-photo { position: relative; width: 100%; aspect-ratio: 4 / 3; border-radius: 0.5rem;
            overflow: hidden; background: rgba(128, 128, 128, 0.12); }
.pm-photo img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pm-photo .pm-fail { display: none; position: absolute; inset: 0; flex-direction: column;
                     align-items: center; justify-content: center; text-align: center;
                     padding: 0.75rem; gap: 0.25rem; color: rgba(128, 128, 128, 0.95);
                     word-break: keep-all; }
.pm-photo .pm-fail b { font-size: 0.9rem; }
.pm-photo .pm-fail small { font-size: 0.75rem; line-height: 1.3; }
.pm-photo.pm-failed img { display: none; }
.pm-photo.pm-failed .pm-fail { display: flex; }
</style>
"""

# 사진을 순서대로 시도하고, 모두 실패하면 안내 문구를 보여줍니다.
_FALLBACK_JS = """
<script>
(function () {
  var box = document.getElementById(%(id)s);
  if (!box || box.dataset.pmReady) return;
  box.dataset.pmReady = "1";
  var img = box.querySelector("img");
  var srcs = JSON.parse(box.dataset.srcs || "[]");
  var i = 0;
  function next() {
    i += 1;
    if (i < srcs.length) { img.src = srcs[i]; } else { box.classList.add("pm-failed"); }
  }
  if (!img) { box.classList.add("pm-failed"); return; }
  img.addEventListener("error", next);
  if (img.complete && img.naturalWidth === 0) next();
})();
</script>
"""


def photo_urls(dog: dict) -> list[str]:
    """popfile1, popfile2, ... 순서로 사용 가능한 사진 주소 목록 (중복 제외)."""
    keyed = []
    for key, value in dog.items():
        m = _POPFILE_RE.match(key)
        if m and isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
            keyed.append((int(m.group(1)), value.strip()))
    urls: list[str] = []
    for _, url in sorted(keyed):
        if url not in urls:
            urls.append(url)
    return urls


def photo_html(dog: dict, element_id: str) -> str:
    """사진 영역 HTML. 사진이 없거나 모두 깨지면 안내 문구가 보입니다."""
    urls = photo_urls(dog)
    fail = (
        f'<div class="pm-fail"><span>🐾</span><b>{PHOTO_FAIL_TITLE}</b>'
        f"<small>{PHOTO_FAIL_DETAIL}</small></div>"
    )
    eid = html.escape(element_id, quote=True)
    if not urls:
        return f'<div class="pm-photo pm-failed" id="{eid}">{fail}</div>'

    alt = html.escape(dog.get("kindFullNm") or dog.get("kindNm") or "보호 중인 강아지", quote=True)
    srcs = html.escape(json.dumps(urls), quote=True)
    first = html.escape(urls[0], quote=True)
    script = _FALLBACK_JS % {"id": json.dumps(element_id)}
    return (
        f'<div class="pm-photo" id="{eid}" data-srcs="{srcs}">'
        f'<img src="{first}" alt="{alt}" loading="lazy" referrerpolicy="no-referrer">{fail}</div>'
        f"{script}"
    )


def inject_card_css() -> None:
    st.html(CARD_CSS)


def render_card(
    dog: dict, distance_km: float | None = None, show_shelter: bool = True, key_prefix: str = "pm"
) -> None:
    element_id = f"{key_prefix}-photo-{dog.get('desertionNo') or id(dog)}"
    st.html(photo_html(dog, element_id), unsafe_allow_javascript=True)
    st.markdown(f"**{dog.get('kindFullNm') or dog.get('kindNm') or '품종 미상'}**")
    lines = [f"{format_age(dog.get('age'))} · {format_sex(dog.get('sexCd'))}"]
    if show_shelter:
        shelter = dog.get("careNm", "")
        lines.append(f"{shelter} · {distance_km:.1f}km" if distance_km is not None else shelter)
    st.caption("\n\n".join(lines))
    status = adoption_status(dog.get("noticeEdt"))
    color = "green" if status == "입양 가능" else "orange"
    st.markdown(f":{color}-badge[{status}]")


def render_grid(dogs: list[dict], columns: int = 4, **card_kwargs) -> None:
    for start in range(0, len(dogs), columns):
        cols = st.columns(columns)
        for col, dog in zip(cols, dogs[start : start + columns]):
            with col:
                render_card(dog, **card_kwargs)
