"""API 원문 값을 화면에 보여주기 좋은 문구로 바꾸는 함수들."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

_AGE_RE = re.compile(r"^\s*(\d{4})\s*(?:\((?!년생)([^)]*)\))?\s*\(년생\)\s*$")

SEX_LABELS = {"M": "수컷", "F": "암컷", "Q": "성별 미상"}


def format_age(raw: str | None) -> str:
    """'2026(60일미만)(년생)' -> '2026년생 · 60일 미만', '2024(년생)' -> '2024년생'."""
    if not raw:
        return "나이 미상"
    m = _AGE_RE.match(raw)
    if not m:
        return raw.strip()
    year, note = m.groups()
    if note:
        note = note.replace("미만", " 미만").replace("이상", " 이상").replace("  ", " ").strip()
        return f"{year}년생 · {note}"
    return f"{year}년생"


def format_sex(code: str | None) -> str:
    return SEX_LABELS.get((code or "").upper(), "성별 미상")


def parse_ymd(raw: str | None) -> date | None:
    """'20261102' -> date(2026, 11, 2). 형식이 맞지 않으면 None."""
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))  # type: ignore[index]
    except (TypeError, ValueError):
        return None


def adoption_status(notice_end: str | None, today: date | None = None) -> str:
    """공고 종료일 기준 상태 문구.

    공고 기간에는 원래 보호자가 찾아갈 수 있도록 기다리고, 기간이 끝나면 입양을 문의할 수 있습니다.
    """
    today = today or date.today()
    end = parse_ymd(notice_end)
    if end is None:
        return "보호 중"
    if end >= today:
        return f"공고 중 · {end.month}/{end.day}까지"
    return "입양 가능"


KST = timezone(timedelta(hours=9))


def format_updated(fetched_at: datetime) -> str:
    """데이터를 받은 시각을 한국 시간으로: '11월 3일 14:23 기준'."""
    t = fetched_at.astimezone(KST)
    return f"{t.month}월 {t.day}일 {t:%H:%M} 기준"


NEUTER_LABELS = {"Y": "했어요", "N": "안 했어요", "U": "확인 안 됨"}


def format_weight(raw: str | None) -> str:
    """'5.6(Kg)' -> '5.6kg'. 읽을 수 없으면 원문 그대로."""
    from pawmatch.traits import parse_weight

    weight = parse_weight(raw)
    if weight is None:
        return (raw or "").strip() or "체중 미상"
    return f"{weight:g}kg"


def format_neuter(code: str | None) -> str:
    return NEUTER_LABELS.get((code or "").upper(), "확인 안 됨")


def format_ymd(raw: str | None) -> str:
    """'20261103' -> '2026. 11. 3.'"""
    d = parse_ymd(raw)
    return f"{d.year}. {d.month}. {d.day}." if d else ""


def _time_range(start: str | None, end: str | None) -> str:
    start, end = (start or "").strip(), (end or "").strip()
    if not start or not end or start == ":" or end == ":":
        return ""
    return f"{start} ~ {end}"


def format_shelter_hours(shelter: dict | None) -> list[str]:
    """보호소 운영 시간·휴무일 문구 목록. 정보가 없으면 빈 목록."""
    if not shelter:
        return []
    lines = []
    weekday = _time_range(shelter.get("weekOprStime"), shelter.get("weekOprEtime"))
    weekend = _time_range(shelter.get("weekendOprStime"), shelter.get("weekendOprEtime"))
    if weekday:
        lines.append(f"평일 {weekday}")
    if weekend:
        lines.append(f"주말 {weekend}")
    close = (shelter.get("closeDay") or "").strip()
    if close and close != "0":
        lines.append(f"휴무 {close.replace('+', ', ')}")
    return lines


def dog_facts(dog: dict) -> list[tuple[str, str]]:
    """상세 정보 창에 보여줄 (항목, 값) 목록. 값이 없는 항목은 뺍니다."""
    notice = " ~ ".join(x for x in (format_ymd(dog.get("noticeSdt")), format_ymd(dog.get("noticeEdt"))) if x)
    found = " · ".join(x for x in (format_ymd(dog.get("happenDt")), (dog.get("happenPlace") or "").strip()) if x)
    facts = [
        ("나이", format_age(dog.get("age"))),
        ("성별", format_sex(dog.get("sexCd"))),
        ("체중", format_weight(dog.get("weight"))),
        ("털색", (dog.get("colorCd") or "").strip()),
        ("중성화", format_neuter(dog.get("neuterYn"))),
        ("발견", found),
        ("공고 기간", notice),
        ("접종", (dog.get("vaccinationChk") or "").strip()),
        ("검사 항목", (dog.get("healthChk") or "").strip()),
        ("공고 번호", (dog.get("noticeNo") or "").strip()),
    ]
    return [(label, value) for label, value in facts if value]


_POPFILE_RE = re.compile(r"^popfile(\d+)$")

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
