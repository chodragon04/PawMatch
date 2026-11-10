"""여러 페이지에서 같이 쓰는 화면 구성 요소 (유기견 카드 등)."""

from __future__ import annotations

import html
import json
from urllib.parse import urlparse

import streamlit as st

from pawmatch.api import ApiError
from pawmatch.config import get_api_key
from pawmatch.data import STORE, WARN_AFTER, Dataset
from pawmatch.display import adoption_status, format_age, format_sex, format_updated, photo_urls, status_badge
from pawmatch.favorites import FAVORITE_CSS, FAVORITE_JS, PAINT_JS, heart_button_html

PHOTO_FAIL_TITLE = "사진을 불러오지 못했어요"
PHOTO_FAIL_DETAIL = "보호소에 문의하면 아이의 모습을 확인할 수 있어요"


CARD_CSS = """
<style>
.pm-photo { position: relative; width: 100%; aspect-ratio: 4 / 3; border-radius: 0.5rem;
            overflow: hidden; background: #FFF4EC; }
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


def photo_html(dog: dict, element_id: str) -> str:
    """사진 영역 HTML. 사진이 없거나 모두 깨지면 안내 문구가 보입니다."""
    urls = photo_urls(dog)
    fail = (
        f'<div class="pm-fail"><span>🐾</span><b>{PHOTO_FAIL_TITLE}</b>'
        f"<small>{PHOTO_FAIL_DETAIL}</small></div>"
    )
    eid = html.escape(element_id, quote=True)
    dog_id = dog.get("desertionNo")
    heart = (heart_button_html(dog_id) + PAINT_JS) if dog_id else ""
    if not urls:
        return f'<div class="pm-photo pm-failed" id="{eid}">{fail}{heart}</div>'

    alt = html.escape(dog.get("kindFullNm") or dog.get("kindNm") or "보호 중인 강아지", quote=True)
    srcs = html.escape(json.dumps(urls), quote=True)
    first = html.escape(urls[0], quote=True)
    script = _FALLBACK_JS % {"id": json.dumps(element_id)}
    return (
        f'<div class="pm-photo" id="{eid}" data-srcs="{srcs}">'
        f'<img src="{first}" alt="{alt}" loading="lazy" referrerpolicy="no-referrer">{fail}{heart}</div>'
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
                         overflow: hidden; background: #FFF4EC; touch-action: pan-y; }
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
.pm-carousel .pm-thumb.pm-on { opacity: 1; border-color: #FF8A3D; }
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
    # 상세 창에도 하트(찜) 버튼. 창은 카드와 따로 그려질 수 있어 하트 동작 코드도 같이 넣습니다(한 번만 등록됨).
    dog_id = dog.get("desertionNo")
    heart = (FAVORITE_CSS + heart_button_html(dog_id) + FAVORITE_JS + PAINT_JS) if dog_id else ""
    if not urls:
        return f'{CAROUSEL_CSS}<div class="pm-carousel pm-failed" id="{eid}"><div class="pm-stage">{fail}{heart}</div></div>'

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
        f'<span class="pm-count"></span>{heart}</div>'
        f'<div class="pm-thumbs">{thumbs}</div></div>'
        f"{_CAROUSEL_JS % {'id': json.dumps(element_id)}}"
    )


NAV_CSS = """
<style>
/* 화면 맨 아래에 고정된 아이콘 탭. 지금 화면은 주황색으로 표시합니다. */
.st-key-pm_nav { position: fixed; left: 0; right: 0; bottom: 0; z-index: 999990; background: #FFFFFF;
                 border-top: 1px solid #F3DCCB; box-shadow: 0 -2px 12px rgba(255, 138, 61, 0.10);
                 padding: 0.25rem 0.5rem calc(0.25rem + env(safe-area-inset-bottom)); }
.st-key-pm_nav [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0 !important;
                                                   max-width: 560px; margin: 0 auto; }
.st-key-pm_nav [data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
.st-key-pm_nav [data-testid="stPageLink"], .st-key-pm_nav [data-testid="stElementContainer"] { width: 100% !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] { flex-direction: column; justify-content: center; align-items: center;
                                                    gap: 0.1rem; padding: 0.35rem 0; border-radius: 0.8rem;
                                                    background: transparent !important; color: #9C8B82; height: auto !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] > span:first-child { height: auto !important; width: auto !important; margin: 0 !important; }
.st-key-pm_nav [data-testid="stVerticalBlock"], .st-key-pm_nav [data-testid="stHorizontalBlock"] { flex: 0 0 auto !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] { font-size: 1.6rem; width: 1.6rem !important; height: 1.6rem !important; line-height: 1; color: #B9A79D; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] p { font-size: 0.7rem; line-height: 1; color: #9C8B82; margin: 0; }
/* 위쪽 메뉴 줄이 없어졌으니 위 여백을 줄이고, 내용이 하단 탭에 가려지지 않게 아래 여백을 둡니다. */
[data-testid="stMainBlockContainer"] { padding-top: 3.5rem !important; padding-bottom: 6rem !important; }
</style>
"""

# 지금 화면의 탭 (key가 pm_nav_<번호>인 칸)
NAV_ACTIVE_CSS = """
<style>
.st-key-pm_nav_%(i)d a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"],
.st-key-pm_nav_%(i)d a[data-testid="stPageLink-NavLink"] p { color: #FF8A3D !important; font-weight: 700; }
</style>
"""

# Streamlit Community Cloud는 공개 앱 화면 오른쪽 아래에 만든 사람 사진과 배지(약 115x46px)를 띄웁니다.
# 앱 바깥(부모 화면)에 있어서 숨길 수 없으므로, 좁은 화면에서는 탭을 왼쪽으로 모아 배지 자리를 비워 둡니다.
# (넓은 화면에서는 탭이 가운데에 모여 있어 겹치지 않음)
NAV_CLOUD_BADGE_CSS = """
<style>
@media (max-width: 800px) {
  .st-key-pm_nav { padding-right: 120px !important; }
  .st-key-pm_nav [data-testid="stHorizontalBlock"] { margin: 0 !important; }
}
</style>
"""
CLOUD_HOST_SUFFIX = ".streamlit.app"


def shows_cloud_badge(url: str | None, embedded: bool = False) -> bool:
    """Streamlit Community Cloud 배지가 보이는 주소인지. (?embed=true로 넣은 화면에는 배지가 없음)"""
    host = urlparse(url or "").hostname or ""
    return host.endswith(CLOUD_HOST_SUFFIX) and not embedded


def render_nav_bar(pages: list, current, short_titles: dict[str, str] | None = None) -> None:
    """화면 맨 아래 고정 아이콘 탭. current(지금 화면)는 주황색으로 표시합니다."""
    short_titles = short_titles or {}
    active = next((i for i, page in enumerate(pages) if page.url_path == current.url_path), -1)
    badge = shows_cloud_badge(st.context.url, st.context.is_embedded)
    st.html(NAV_CSS + NAV_ACTIVE_CSS % {"i": active} + (NAV_CLOUD_BADGE_CSS if badge else ""))
    with st.container(key="pm_nav"):
        for i, (col, page) in enumerate(zip(st.columns(len(pages)), pages)):
            with col, st.container(key=f"pm_nav_{i}"):
                st.page_link(page, label=short_titles.get(page.title, page.title), icon=page.icon)


def page_header(title: str) -> None:
    """각 화면 맨 위의 화면 이름 (굵게, 짧게)."""
    st.markdown(f"## {title}")


def inject_card_css() -> None:
    """카드 모양과 찜(하트) 버튼 동작을 화면에 넣습니다. 카드를 그리기 전에 한 번 부릅니다."""
    st.html(CARD_CSS + FAVORITE_CSS + FAVORITE_JS, unsafe_allow_javascript=True)


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
    st.markdown(status_badge(adoption_status(dog.get("noticeEdt"))))


def render_grid(dogs: list[dict], columns: int = 4, **card_kwargs) -> None:
    for start in range(0, len(dogs), columns):
        cols = st.columns(columns)
        for col, dog in zip(cols, dogs[start : start + columns]):
            with col:
                render_card(dog, **card_kwargs)
