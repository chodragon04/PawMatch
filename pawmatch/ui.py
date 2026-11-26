# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""여러 페이지에서 같이 쓰는 화면 구성 요소 (유기견 카드 등)."""

from __future__ import annotations

import html
import json
import re
from urllib.parse import urlparse

import streamlit as st

from pawmatch.api import ApiError
from pawmatch.colors import ROOT_CSS
from pawmatch.config import get_api_key
from pawmatch.data import STORE, WARN_AFTER, Dataset
from pawmatch.display import dog_label, format_updated, photo_urls
from pawmatch.favorites import FAVORITE_CSS, FAVORITE_JS, PAINT_JS, heart_button_html

PHOTO_FAIL_TITLE = "사진을 불러오지 못했어요"
PHOTO_FAIL_DETAIL = "보호소에 문의하면 아이의 모습을 확인할 수 있어요"


CARD_CSS = """
<style>
.pm-photo { position: relative; width: 100%; aspect-ratio: 4 / 3; border-radius: 0.5rem;
            overflow: hidden; background: var(--pm-peach); }
.pm-photo img { width: 100%; height: 100%; object-fit: contain; display: block; }
.pm-photo .pm-fail { display: none; position: absolute; inset: 0; flex-direction: column;
                     align-items: center; justify-content: center; text-align: center;
                     padding: 0.75rem; gap: 0.25rem; color: var(--pm-muted);
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
        f'<div class="pm-fail"><b>{PHOTO_FAIL_TITLE}</b>'
        f"<small>{PHOTO_FAIL_DETAIL}</small></div>"
    )
    eid = html.escape(element_id, quote=True)
    dog_id = dog.get("desertionNo")
    label = dog_label(dog)
    heart = (heart_button_html(dog_id, label) + PAINT_JS) if dog_id else ""
    data_label = html.escape(label, quote=True)  # 카드의 '자세히 보기' 버튼 이름에도 씀 (A11Y_JS)
    if not urls:
        return f'<div class="pm-photo pm-failed" id="{eid}" data-label="{data_label}">{fail}{heart}</div>'

    alt = html.escape(f"{label} 사진", quote=True)
    srcs = html.escape(json.dumps(urls), quote=True)
    first = html.escape(urls[0], quote=True)
    script = _FALLBACK_JS % {"id": json.dumps(element_id)}
    return (
        f'<div class="pm-photo" id="{eid}" data-label="{data_label}" data-srcs="{srcs}">'
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
                         overflow: hidden; background: var(--pm-peach); touch-action: pan-y; }
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
.pm-carousel .pm-thumb.pm-on { opacity: 1; border-color: var(--pm-orange-icon); }
.pm-carousel .pm-nav:focus-visible, .pm-carousel .pm-thumb:focus-visible { outline: 3px solid var(--pm-orange-icon);
                                                                            outline-offset: 2px; opacity: 1; }
.pm-carousel.pm-single .pm-nav, .pm-carousel.pm-single .pm-count,
.pm-carousel.pm-single .pm-thumbs { display: none; }
.pm-carousel .pm-fail { display: none; position: absolute; inset: 0; flex-direction: column; align-items: center;
                        justify-content: center; gap: 0.25rem; color: var(--pm-muted); }
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
    function pick() { var ok = alive(); show(ok.indexOf(slides[i])); }
    t.addEventListener("click", pick);
    t.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); }
    });
  });
  // PC 키보드: 캐러셀 안(넘김 버튼·썸네일·하트)에 포커스가 있으면 ←/→로 사진을 넘깁니다.
  box.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { e.preventDefault(); show(current - 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); show(current + 1); }
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
    fail = f'<div class="pm-fail"><b>{PHOTO_FAIL_TITLE}</b><small>{PHOTO_FAIL_DETAIL}</small></div>'
    # 상세 창에도 하트(찜) 버튼. 창은 카드와 따로 그려질 수 있어 하트 동작 코드도 같이 넣습니다(한 번만 등록됨).
    dog_id = dog.get("desertionNo")
    heart = (FAVORITE_CSS + heart_button_html(dog_id, dog_label(dog)) + FAVORITE_JS + PAINT_JS) if dog_id else ""
    if not urls:
        return f'{CAROUSEL_CSS}<div class="pm-carousel pm-failed" id="{eid}"><div class="pm-stage">{fail}{heart}</div></div>'

    slides = "".join(
        f'<img class="pm-slide" src="{html.escape(u, quote=True)}" alt="{alt} 사진 {i + 1}" '
        f'referrerpolicy="no-referrer">'
        for i, u in enumerate(urls)
    )
    thumbs = "".join(
        f'<img class="pm-thumb" src="{html.escape(u, quote=True)}" alt="사진 {i + 1} 보기" tabindex="0" role="button" '
        f'referrerpolicy="no-referrer">'
        for i, u in enumerate(urls)
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
__ROOT__
/* 캡션(카드의 나이·보호소, 안내 문구): Streamlit은 글자를 60%로 흐리게 해서 대비가 3.79 → 진한 회색, 흐림 없음 */
[data-testid="stCaptionContainer"] { color: var(--pm-muted) !important; opacity: 1 !important; }
[data-testid="stCaptionContainer"] p { color: var(--pm-muted) !important; }
/* 주황 버튼의 흰 글자는 대비가 낮아(2.35) 진한 갈색 글자로 */
[data-testid^="stBaseButton-primary"], [data-testid^="stBaseButton-primary"] p { color: var(--pm-text) !important; }
/* 화면 이름(h1): Streamlit 기본 위 여백이 커서 예전(h2) 위치에 맞춤 */
[data-testid="stHeading"] h1 { padding-top: 0.25rem !important; }
/* 브라우저 값을 읽는 보이지 않는 칸(내 위치, 찜 목록: streamlit_js_eval)이 빈 자리를 만들지 않게 높이 0 (동작은 그대로) */
[data-testid="stElementContainer"]:has(iframe[title="streamlit_js_eval.streamlit_js_eval"]) {
  height: 0 !important; min-height: 0 !important; overflow: hidden; margin: 0 !important; }
/* 알약 버튼: 손가락으로 누르기 쉽게 높이 44px (기본 32px) */
button[data-variant="pills"] { min-height: 2.75rem; }
/* 고른 알약 버튼 글자 */
[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[aria-pressed="true"] p { color: var(--pm-orange-text) !important; }
/* 화면 맨 아래에 고정된 아이콘 탭. 지금 화면은 주황색으로 표시합니다. */
.st-key-pm_nav { position: fixed; left: 0; right: 0; bottom: 0; z-index: 999990; background: #FFFFFF;
                 border-top: 1px solid var(--pm-line); box-shadow: 0 -2px 12px rgba(255, 138, 61, 0.10);
                 padding: 0.25rem 0.5rem calc(0.25rem + env(safe-area-inset-bottom)); }
.st-key-pm_nav [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0 !important;
                                                   max-width: 560px; margin: 0 auto; }
.st-key-pm_nav [data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
.st-key-pm_nav [data-testid="stPageLink"], .st-key-pm_nav [data-testid="stElementContainer"] { width: 100% !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] { flex-direction: column; justify-content: center; align-items: center;
                                                    gap: 0.1rem; padding: 0.35rem 0; border-radius: 0.8rem;
                                                    background: transparent !important; color: var(--pm-muted); height: auto !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] > span:first-child { height: auto !important; width: auto !important; margin: 0 !important; }
.st-key-pm_nav [data-testid="stVerticalBlock"], .st-key-pm_nav [data-testid="stHorizontalBlock"] { flex: 0 0 auto !important; }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] { font-size: 1.6rem; width: 1.6rem !important; height: 1.6rem !important; line-height: 1; color: var(--pm-muted); }
.st-key-pm_nav a[data-testid="stPageLink-NavLink"] p { font-size: 0.75rem; line-height: 1.1; color: var(--pm-muted); margin: 0; }
/* PC 키보드(Tab)로 링크에 왔을 때 위치가 보이게 (Streamlit 기본은 표시가 없음) */
a[data-testid="stPageLink-NavLink"]:focus-visible { outline: 3px solid var(--pm-orange-icon) !important; outline-offset: 2px; }
/* PC에서 마우스를 올리면 하단 탭에 옅은 배경 (휴대폰은 마우스가 없어 해당 없음) */
@media (hover: hover) {
  .st-key-pm_nav a[data-testid="stPageLink-NavLink"]:hover { background: var(--pm-peach) !important; }
  .st-key-pm_nav a[data-testid="stPageLink-NavLink"]:hover p,
  .st-key-pm_nav a[data-testid="stPageLink-NavLink"]:hover span[data-testid="stIconMaterial"] { color: var(--pm-text); }
}
/* 위쪽 메뉴 줄이 없어졌으니 위 여백을 줄이고, 내용이 하단 탭에 가려지지 않게 아래 여백을 둡니다. */
[data-testid="stMainBlockContainer"] { padding-top: 3.5rem !important; padding-bottom: 6rem !important; }
/* 넓은 PC 화면에서 입력칸·카드가 끝까지 늘어나지 않게 내용 폭을 1280px(좌우 여백 포함)까지로 하고 가운데에 둡니다. */
[data-testid="stMainBlockContainer"] { max-width: 1280px; margin-left: auto; margin-right: auto; }
</style>
""".replace("__ROOT__", ROOT_CSS)

# 지금 화면의 탭 (key가 pm_nav_<번호>인 칸): 아이콘은 아이콘용 주황, 글자는 글자용 진한 주황
NAV_ACTIVE_CSS = """
<style>
.st-key-pm_nav_%(i)d a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] { color: var(--pm-orange-icon) !important; }
.st-key-pm_nav_%(i)d a[data-testid="stPageLink-NavLink"] p { color: var(--pm-orange-text) !important; font-weight: 700; }
</style>
"""

# 위쪽 메뉴와 오른쪽 위 Streamlit 버튼(⋮, 배포 사이트에서는 Share·☆·✎·GitHub도) 사이 간격.
# 버튼 크기가 화면 크기와 상관없이 고정(px)이라 간격도 고정으로 둡니다. 버튼 폭(--pm-toolbar-w)은 화면에서 잽니다(A11Y_JS).
TOOLBAR_GAP_PX = 24
# PC(폭 1024px 이상): 아이콘 탭을 화면 위쪽 메뉴 줄로 옮기고, 왼쪽에 'PawMatch'(홈으로)를 둡니다.
# 휴대폰·태블릿 세로 화면은 지금처럼 하단 탭. 메뉴 줄 안쪽 폭은 본문(1280px, 좌우 5rem 여백)과 맞춥니다.
# z-index는 Streamlit 위쪽 도구 줄(⋮ 메뉴)보다 한 단계 낮게 해서 ⋮ 버튼을 가리지 않습니다.
NAV_BRAND_KEY = "pm_brand"
NAV_TOP_CSS = """
<style>
:root { --pm-toolbar-gap: __GAP__px; }
/* 휴대폰: 'PawMatch'와 그 바깥 칸까지 숨겨서 하단 탭 높이가 그대로이게 */
.st-key-pm_brand, [data-testid="stLayoutWrapper"]:has(> .st-key-pm_brand) { display: none !important; }
@media (min-width: 1024px) {
  .st-key-pm_nav { top: 0; bottom: auto; z-index: 999989; border-top: none; border-bottom: 1px solid var(--pm-line);
                   box-shadow: 0 2px 12px rgba(255, 138, 61, 0.08); flex-direction: row !important;
                   align-items: center; justify-content: space-between; min-height: 3.75rem;
                   padding: 0.35rem max(5rem, calc((100vw - 1120px) / 2)) !important;
                   padding-right: max(5rem, calc((100vw - 1120px) / 2),
                                      calc(var(--pm-toolbar-w, 3rem) + var(--pm-toolbar-gap))) !important; }
  .st-key-pm_brand, [data-testid="stLayoutWrapper"]:has(> .st-key-pm_brand) {
    display: flex !important; width: auto !important; flex: 0 0 auto !important; }
  .st-key-pm_brand a[data-testid="stPageLink-NavLink"] { flex-direction: row !important; gap: 0.35rem;
                                                         background: transparent !important; padding: 0.25rem 0; }
  .st-key-pm_brand a[data-testid="stPageLink-NavLink"] p { font-family: "Jua", sans-serif; font-size: 1.45rem;
                                                           color: var(--pm-text); }
  .st-key-pm_brand a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] {
    color: var(--pm-orange-icon); font-size: 1.6rem; }
  .st-key-pm_nav > [data-testid="stLayoutWrapper"], .st-key-pm_nav [data-testid="stHorizontalBlock"] {
    width: auto !important; max-width: none !important; margin: 0 !important; flex: 0 0 auto !important; gap: 0.25rem !important; }
  .st-key-pm_nav [data-testid="stColumn"] { flex: 0 0 auto !important; width: auto !important; }
  .st-key-pm_nav [class*="st-key-pm_nav_"] a[data-testid="stPageLink-NavLink"] { flex-direction: row; gap: 0.4rem;
                                                                                 padding: 0.45rem 0.8rem; }
  .st-key-pm_nav [class*="st-key-pm_nav_"] a[data-testid="stPageLink-NavLink"] span[data-testid="stIconMaterial"] {
    font-size: 1.3rem; width: 1.3rem !important; height: 1.3rem !important; }
  .st-key-pm_nav [class*="st-key-pm_nav_"] a[data-testid="stPageLink-NavLink"] p { font-size: 0.95rem; }
  /* Streamlit 위쪽 도구 줄(⋮)은 흰 배경이라 메뉴를 가림 → 투명하게 해서 메뉴 위에 ⋮ 버튼만 보이게 */
  /* 투명해도 메뉴 위를 덮어 클릭을 막으므로, 클릭은 아래 메뉴로 통과시키고 ⋮ 도구 줄만 클릭되게 */
  [data-testid="stHeader"], [data-testid="stHeader"] * { pointer-events: none; }
  [data-testid="stHeader"] { background: transparent !important; }
  [data-testid="stHeader"] button, [data-testid="stHeader"] a { pointer-events: auto; }
  /* 메뉴가 위로 갔으니 본문 위 여백을 늘리고 아래 여백(하단 탭 자리)은 줄임 */
  [data-testid="stMainBlockContainer"] { padding-top: 5rem !important; padding-bottom: 3rem !important; }
}
</style>
""".replace("__GAP__", str(TOOLBAR_GAP_PX))

# Streamlit Community Cloud는 공개 앱 화면 오른쪽 아래에 만든 사람 사진과 배지(약 115x46px)를 띄웁니다.
# 앱 바깥(부모 화면)에 있어서 숨길 수 없으므로, 좁은 화면에서는 탭을 왼쪽으로 모아 배지 자리를 비워 둡니다.
# (넓은 화면에서는 탭이 가운데에 모여 있어 겹치지 않음. 탭 오른쪽 끝 = 폭/2 + 280px, 배지 왼쪽 끝 ≈ 폭 - 131px
#  이므로 폭 822px 이하에서 겹침 → 여유를 두고 860px까지 왼쪽으로 모음)
NAV_CLOUD_BADGE_CSS = """
<style>
/* 배포 사이트는 오른쪽 위에 Share·☆·✎·GitHub·⋮ 버튼이 붙음: 화면에서 재기 전까지 쓸 폭 (A11Y_JS가 실제 폭으로 바꿈) */
:root { --pm-toolbar-w: 220px; }
@media (max-width: 860px) {
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


# Streamlit이 영어로 보여주는 부분을 한국어로 (CSS·설정으로 바꿀 수 없는 글자)
KOREAN_LABELS = {
    "Upload": "사진 고르기",  # 파일 올리기 버튼
    "Take Photo": "사진 찍기",  # 카메라
    "Clear photo": "다시 찍기",
}
UPLOAD_LIMIT_TEXT = "10MB까지 · JPG, PNG, WEBP"  # 원래: '10MB per file • JPG, PNG, WEBP'
UPLOAD_LIMIT_TEXT_PC = "여기로 끌어다 놓아도 돼요 · " + UPLOAD_LIMIT_TEXT  # 마우스가 있는 PC에서만

# 접근성 보정: 페이지 언어(한국어), 하단 탭의 지금 화면 표시(aria-current), 영어 글자 한국어로.
# Streamlit이 화면을 다시 그릴 때마다 되돌아가므로, 바뀔 때마다 다시 맞춥니다. (한 번만 등록)
A11Y_JS = """
<script>
(function () {
  window.__pmNavActive = __ACTIVE__;
  if (window.__pmA11y) { window.__pmA11yApply && window.__pmA11yApply(); return; }
  window.__pmA11y = true;
  var LABELS = __LABELS__, LIMIT = __LIMIT__, LIMIT_PC = __LIMIT_PC__;
  var PC = window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  function apply() {
    var doc = document.documentElement;
    if (doc.lang !== "ko") doc.lang = "ko";
    document.querySelectorAll(".st-key-pm_nav [class*='st-key-pm_nav_'] a").forEach(function (a, i) {
      if (i === window.__pmNavActive) { a.setAttribute("aria-current", "page"); } else { a.removeAttribute("aria-current"); }
    });
    document.querySelectorAll("[data-testid=stFileUploaderDropzone] button p, [data-testid=stCameraInputButton]").forEach(function (el) {
      var t = el.textContent.trim();
      if (LABELS[t]) el.textContent = LABELS[t];
    });
    document.querySelectorAll("[data-testid=stFileUploaderDropzoneInstructions] span").forEach(function (el) {
      if (/per file/.test(el.textContent)) el.textContent = PC ? LIMIT_PC : LIMIT;
    });
    document.querySelectorAll("[data-testid=stFileUploaderDropzoneInput]").forEach(function (el) {
      if (el.getAttribute("aria-label") === "file upload") el.setAttribute("aria-label", "사진 파일 고르기");
    });
    document.querySelectorAll("[class*='st-key-pm_card_']").forEach(function (card) {
      var photo = card.querySelector(".pm-photo[data-label]");
      if (!photo) return;
      card.querySelectorAll("[data-testid=stButton] button").forEach(function (b) {
        var name = b.innerText.trim() + ": " + photo.dataset.label;
        if (b.getAttribute("aria-label") !== name) b.setAttribute("aria-label", name);
      });
    });
    document.querySelectorAll("button[aria-label^='Help for ']").forEach(function (el) {
      el.setAttribute("aria-label", "도움말: " + el.getAttribute("aria-label").slice(9));
    });
  }
  // 오른쪽 위 Streamlit 버튼들(⋮, 배포 사이트의 Share 등)이 차지하는 폭을 재서 위쪽 메뉴가 비켜 가게 (PC)
  function measureToolbar() {
    var left = Infinity;
    document.querySelectorAll("[data-testid=stHeader] button, [data-testid=stHeader] a").forEach(function (b) {
      var r = b.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) left = Math.min(left, r.left);
    });
    if (left === Infinity) return;
    var w = Math.ceil(document.documentElement.clientWidth - left) + "px";
    if (document.documentElement.style.getPropertyValue("--pm-toolbar-w") !== w) {
      document.documentElement.style.setProperty("--pm-toolbar-w", w);
    }
  }
  var applyBase = apply;
  apply = function () { applyBase(); measureToolbar(); };
  window.addEventListener("resize", function () { requestAnimationFrame(measureToolbar); });
  window.__pmA11yApply = apply;
  var queued = false;
  new MutationObserver(function () {
    if (queued) return;
    queued = true;
    requestAnimationFrame(function () { queued = false; apply(); });
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
  apply();
})();
</script>
"""


def a11y_script(active: int) -> str:
    return (
        A11Y_JS.replace("__ACTIVE__", str(int(active)))
        .replace("__LABELS__", json.dumps(KOREAN_LABELS, ensure_ascii=False))
        .replace("__LIMIT_PC__", json.dumps(UPLOAD_LIMIT_TEXT_PC, ensure_ascii=False))
        .replace("__LIMIT__", json.dumps(UPLOAD_LIMIT_TEXT, ensure_ascii=False))
    )


def render_nav_bar(pages: list, current, short_titles: dict[str, str] | None = None) -> None:
    """화면 맨 아래 고정 아이콘 탭. current(지금 화면)는 주황색으로 표시합니다."""
    short_titles = short_titles or {}
    active = next((i for i, page in enumerate(pages) if page.url_path == current.url_path), -1)
    badge = shows_cloud_badge(st.context.url, st.context.is_embedded)
    st.html(NAV_CSS + NAV_ACTIVE_CSS % {"i": active} + (NAV_CLOUD_BADGE_CSS if badge else "") + NAV_TOP_CSS)
    st.html(a11y_script(active), unsafe_allow_javascript=True)
    with st.container(key="pm_nav"):
        with st.container(key=NAV_BRAND_KEY):  # PC 위쪽 메뉴에서만 보이는 'PawMatch' (홈으로)
            st.page_link(pages[0], label="PawMatch", icon=":material/pets:")
        for i, (col, page) in enumerate(zip(st.columns(len(pages)), pages)):
            with col, st.container(key=f"pm_nav_{i}"):
                st.page_link(page, label=short_titles.get(page.title, page.title), icon=page.icon)


def page_header(title: str) -> None:
    """각 화면 맨 위의 화면 이름. 화면마다 하나뿐인 가장 큰 제목(h1)입니다."""
    st.title(title, anchor=False)


def inject_card_css() -> None:
    """카드 모양과 찜(하트) 버튼 동작을 화면에 넣습니다. 카드를 그리기 전에 한 번 부릅니다."""
    st.html(CARD_CSS + FAVORITE_CSS + FAVORITE_JS, unsafe_allow_javascript=True)


_PHONE_UA = re.compile(r"iPhone|iPod|Android.*Mobile|Mobile.*Firefox|Windows Phone", re.IGNORECASE)


def is_phone(user_agent: str | None = None) -> bool:
    """휴대폰 브라우저인지 (User-Agent로 판단). 태블릿과 PC는 False.

    화면 처음 모양(예: 검색 조건을 펼쳐 둘지)을 정할 때만 씁니다. 모를 때는 PC로 봅니다.
    """
    if user_agent is None:
        try:
            user_agent = st.context.headers.get("User-Agent", "")
        except Exception:  # 화면 테스트(AppTest) 등 요청 정보가 없을 때
            user_agent = ""
    return bool(_PHONE_UA.search(user_agent or ""))


_SCROLL_JS = """
<script>
(function () {
  // %(nonce)s: 제출할 때마다 글이 달라져서 다시 실행됩니다.
  // 화면을 다시 그리는 동안 스크롤 위치가 되돌아갈 수 있어서, 1.5초 동안 몇 번 확인하며 맞춥니다.
  var tries = 0;
  (function go() {
    var el = document.querySelector(".st-key-%(key)s");
    if (el) {
      el.style.scrollMarginTop = "4.5rem";  // 위쪽 메뉴(⋮) 줄에 제목이 가리지 않게
      var top = el.getBoundingClientRect().top;
      if (Math.abs(top - 72) > 24) el.scrollIntoView({ block: "start" });
    }
    if (tries++ < 15) setTimeout(go, 100);
  })();
})();
</script>
"""


def scroll_to(key: str, nonce: int) -> None:
    """key가 key인 칸(st.container(key=...))이 화면 맨 위에 오게 스크롤합니다. (제출 직후 결과로 이동)"""
    st.html(_SCROLL_JS % {"key": key, "nonce": nonce}, unsafe_allow_javascript=True)
