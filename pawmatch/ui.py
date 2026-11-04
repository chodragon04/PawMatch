"""여러 페이지에서 같이 쓰는 화면 구성 요소 (유기견 카드 등)."""

from __future__ import annotations

import html
import json
import re

import streamlit as st

from pawmatch.api import ApiError
from pawmatch.config import get_api_key
from pawmatch.data import STORE, WARN_AFTER, Dataset
from pawmatch.display import adoption_status, format_age, format_sex, format_updated

PHOTO_FAIL_TITLE = "사진을 불러오지 못했어요"
PHOTO_FAIL_DETAIL = "보호소에 문의하면 아이의 모습을 확인할 수 있어요"

_POPFILE_RE = re.compile(r"^popfile(\d+)$")

CARD_CSS = """
<style>
.pm-photo { position: relative; width: 100%; aspect-ratio: 4 / 3; border-radius: 0.5rem;
            overflow: hidden; background: rgba(128, 128, 128, 0.12); }
.pm-photo img { width: 100%; height: 100%; object-fit: contain; display: block; }
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


# 국가동물보호정보시스템 사진 서버는 https도 지원하지만 API는 http 주소를 줍니다.
# https 페이지에서 http 사진을 섞어 쓰지 않도록 https로 바꿔 씁니다.
_HTTPS_PHOTO_HOSTS = ("openapi.animal.go.kr",)


def _prefer_https(url: str) -> str:
    for host in _HTTPS_PHOTO_HOSTS:
        prefix = f"http://{host}/"
        if url.lower().startswith(prefix):
            return f"https://{host}/" + url[len(prefix) :]
    return url


def photo_urls(dog: dict) -> list[str]:
    """popfile1, popfile2, ... 순서로 사용 가능한 사진 주소 목록 (중복 제외)."""
    keyed = []
    for key, value in dog.items():
        m = _POPFILE_RE.match(key)
        if m and isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
            keyed.append((int(m.group(1)), _prefer_https(value.strip())))
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


def load_data_or_stop() -> Dataset:
    """보호견·보호소 데이터를 불러옵니다. 실패하면 안내를 보여주고 페이지를 멈춥니다."""
    try:
        with st.spinner("보호 중인 아이들을 불러오는 중..."):
            data = STORE.get(get_api_key())
    except ApiError as exc:
        st.error(f"유기견 정보를 불러오지 못했습니다.\n\n{exc}")
        st.stop()
    if data.age() > WARN_AFTER:
        st.warning(f"{format_updated(data.fetched_at)} 정보예요. 최신 정보를 받는 중이니 잠시 뒤 새로고침해 주세요.")
    return data


CAROUSEL_CSS = """
<style>
.pm-carousel { position: relative; width: 100%; }
.pm-carousel .pm-stage { position: relative; width: 100%; height: min(62vh, 520px); border-radius: 0.5rem;
                         overflow: hidden; background: rgba(128, 128, 128, 0.12); touch-action: pan-y; }
.pm-carousel .pm-slide { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain;
                         display: none; }
.pm-carousel .pm-slide.pm-on { display: block; }
.pm-carousel .pm-nav { position: absolute; top: 50%; transform: translateY(-50%); width: 2.5rem; height: 2.5rem;
                       border: none; border-radius: 50%; background: rgba(0, 0, 0, 0.45); color: #fff;
                       font-size: 1.4rem; line-height: 1; cursor: pointer; }
.pm-carousel .pm-nav:hover { background: rgba(0, 0, 0, 0.65); }
.pm-carousel .pm-prev { left: 0.5rem; }
.pm-carousel .pm-next { right: 0.5rem; }
.pm-carousel .pm-count { position: absolute; right: 0.6rem; bottom: 0.6rem; padding: 0.1rem 0.5rem;
                         border-radius: 1rem; background: rgba(0, 0, 0, 0.5); color: #fff; font-size: 0.8rem; }
.pm-carousel .pm-thumbs { display: flex; gap: 0.4rem; margin-top: 0.5rem; overflow-x: auto; }
.pm-carousel .pm-thumb { flex: 0 0 auto; width: 4rem; height: 3rem; object-fit: cover; border-radius: 0.3rem;
                         cursor: pointer; opacity: 0.55; border: 2px solid transparent; }
.pm-carousel .pm-thumb.pm-on { opacity: 1; border-color: #7c5cff; }
.pm-carousel.pm-single .pm-nav, .pm-carousel.pm-single .pm-count,
.pm-carousel.pm-single .pm-thumbs { display: none; }
.pm-carousel .pm-fail { display: none; position: absolute; inset: 0; flex-direction: column; align-items: center;
                        justify-content: center; gap: 0.25rem; color: rgba(128, 128, 128, 0.95); }
.pm-carousel.pm-failed .pm-fail { display: flex; }
.pm-carousel.pm-failed .pm-nav, .pm-carousel.pm-failed .pm-count, .pm-carousel.pm-failed .pm-thumbs { display: none; }
</style>
"""

# 사진을 넘겨 볼 수 있는 캐러셀. 깨진 사진은 건너뛰고, 모두 깨지면 안내 문구를 보여줍니다.
_CAROUSEL_JS = """
<script>
(function () {
  var box = document.getElementById(%(id)s);
  if (!box || box.dataset.pmReady) return;
  box.dataset.pmReady = "1";
  var slides = [].slice.call(box.querySelectorAll(".pm-slide"));
  var thumbs = [].slice.call(box.querySelectorAll(".pm-thumb"));
  var count = box.querySelector(".pm-count");
  var current = 0;
  function alive() { return slides.filter(function (s) { return !s.dataset.broken; }); }
  function show(n) {
    var ok = alive();
    if (!ok.length) { box.classList.add("pm-failed"); return; }
    current = (n + ok.length) %% ok.length;
    var target = ok[current];
    slides.forEach(function (s, i) {
      var on = s === target;
      s.classList.toggle("pm-on", on);
      if (thumbs[i]) {
        thumbs[i].classList.toggle("pm-on", on);
        thumbs[i].style.display = s.dataset.broken ? "none" : "";
      }
    });
    count.textContent = (current + 1) + " / " + ok.length;
    box.classList.toggle("pm-single", ok.length < 2);
  }
  slides.forEach(function (s) {
    s.addEventListener("error", function () { s.dataset.broken = "1"; show(current); });
    if (s.complete && s.naturalWidth === 0) s.dataset.broken = "1";
  });
  thumbs.forEach(function (t, i) {
    t.addEventListener("click", function () { var ok = alive(); show(ok.indexOf(slides[i])); });
  });
  box.querySelector(".pm-prev").addEventListener("click", function () { show(current - 1); });
  box.querySelector(".pm-next").addEventListener("click", function () { show(current + 1); });
  var startX = null;
  var stage = box.querySelector(".pm-stage");
  stage.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener("touchend", function (e) {
    if (startX === null) return;
    var dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 40) show(current + (dx < 0 ? 1 : -1));
    startX = null;
  });
  show(0);
})();
</script>
"""


def carousel_html(dog: dict, element_id: str) -> str:
    """유기견 사진 전체를 넘겨 볼 수 있는 캐러셀 HTML (사진 원본 비율 유지)."""
    urls = photo_urls(dog)
    eid = html.escape(element_id, quote=True)
    alt = html.escape(dog.get("kindFullNm") or dog.get("kindNm") or "보호 중인 강아지", quote=True)
    fail = f'<div class="pm-fail"><span>🐾</span><b>{PHOTO_FAIL_TITLE}</b><small>{PHOTO_FAIL_DETAIL}</small></div>'
    if not urls:
        return f'{CAROUSEL_CSS}<div class="pm-carousel pm-failed" id="{eid}"><div class="pm-stage">{fail}</div></div>'

    slides = "".join(
        f'<img class="pm-slide" src="{html.escape(u, quote=True)}" alt="{alt} 사진 {i + 1}" '
        f'referrerpolicy="no-referrer">'
        for i, u in enumerate(urls)
    )
    thumbs = "".join(
        f'<img class="pm-thumb" src="{html.escape(u, quote=True)}" alt="" referrerpolicy="no-referrer">' for u in urls
    )
    return (
        f'{CAROUSEL_CSS}<div class="pm-carousel" id="{eid}">'
        f'<div class="pm-stage">{slides}{fail}'
        f'<button type="button" class="pm-nav pm-prev" aria-label="이전 사진">‹</button>'
        f'<button type="button" class="pm-nav pm-next" aria-label="다음 사진">›</button>'
        f'<span class="pm-count"></span></div>'
        f'<div class="pm-thumbs">{thumbs}</div></div>'
        f"{_CAROUSEL_JS % {'id': json.dumps(element_id)}}"
    )


NAV_CSS = """
<style>
/* 화면 위 바로가기 버튼 줄: 좁은 화면에서도 한 줄로 두고, 넘치면 옆으로 밀어서 봅니다. */
.st-key-pm_nav [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; overflow-x: auto;
                                                   gap: 0.4rem; scrollbar-width: none; }
.st-key-pm_nav [data-testid="stHorizontalBlock"]::-webkit-scrollbar { display: none; }
.st-key-pm_nav [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important;
                                          min-width: max-content !important; }
.st-key-pm_nav a { border: 1px solid rgba(128, 128, 128, 0.35); border-radius: 999px; padding: 0.1rem 0.75rem; }
</style>
"""


def render_nav_bar(pages: list) -> None:
    """모든 화면 위에 보이는 바로가기 버튼 줄. 지금 화면은 강조 표시됩니다."""
    st.html(NAV_CSS)
    with st.container(key="pm_nav"):
        for col, page in zip(st.columns(len(pages)), pages):
            col.page_link(page, label=page.title, icon=page.icon)


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
