"""보호견 둘러보기: 조건(지역, 크기, 나이, 성별, 상태, 품종, 검색어)으로 거르고 정렬합니다.

지역은 보호소 주소로 판단하므로, 보호소 좌표를 찾지 못한 아이도 빠지지 않습니다.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date

from pawmatch import traits as T
from pawmatch.display import parse_ymd
from pawmatch.geo import address_in_area
from pawmatch.matching import MatchResult, Survey, breed_name, score_dog

# ---------------------------------------------------------------- 선택지

NOTICE, ADOPTABLE = "notice", "adoptable"
STATUS_LABELS = {NOTICE: "공고 중", ADOPTABLE: "입양 가능"}

UNKNOWN_SIZE = "unknown"
SIZE_FILTER_LABELS = {
    T.SMALL: "소형 (10kg 미만)",
    T.MEDIUM: "중형 (10~25kg)",
    T.LARGE: "대형 (25kg 이상)",
    UNKNOWN_SIZE: "크기 예측 어려움",
}

RECENT, DEADLINE, LONGEST, FIT = "recent", "deadline", "longest", "fit"
SORT_LABELS = {RECENT: "최근 등록순", DEADLINE: "공고 마감 임박순", LONGEST: "오래 기다린 순", FIT: "나와 잘 맞는 순"}

KEYWORD_FIELDS = ("kindNm", "kindFullNm", "colorCd", "specialMark", "careNm", "careAddr", "happenPlace", "noticeNo")


@dataclass(frozen=True)
class BrowseFilter:
    sido: str | None = None  # None이면 전국
    sigungu: str | None = None  # None이면 시/도 전체
    sizes: frozenset[str] = frozenset()  # 비어 있으면 전부
    ages: frozenset[str] = frozenset()
    sex: str | None = None  # "M" / "F" / None(전부)
    statuses: frozenset[str] = frozenset()
    breeds: frozenset[str] = frozenset()
    keyword: str = ""


def notice_status(dog: dict, today: date | None = None) -> str | None:
    """공고 종료일 기준 상태: 공고 중(종료일 포함) / 입양 가능(종료일 지남) / 모름(None)."""
    end = parse_ymd(dog.get("noticeEdt"))
    if end is None:
        return None
    return NOTICE if end >= (today or date.today()) else ADOPTABLE


def _keyword_match(dog: dict, keyword: str) -> bool:
    """검색어를 띄어쓰기로 나눠 모든 낱말이 정보 어딘가에 들어 있으면 통과 (대소문자 무시)."""
    words = keyword.casefold().split()
    if not words:
        return True
    text = " ".join(str(dog.get(field) or "") for field in KEYWORD_FIELDS).casefold()
    return all(word in text for word in words)


def matches(dog: dict, f: BrowseFilter, today: date | None = None) -> bool:
    if f.sido and not address_in_area(dog.get("careAddr"), f.sido, f.sigungu):
        return False
    if f.sex and (dog.get("sexCd") or "").upper() != f.sex:
        return False
    if f.statuses and notice_status(dog, today) not in f.statuses:
        return False
    if f.breeds and breed_name(dog) not in f.breeds:
        return False
    if f.sizes or f.ages:
        p = T.profile(dog, today)
        if f.sizes and (p.size or UNKNOWN_SIZE) not in f.sizes:
            return False
        if f.ages and p.age_group not in f.ages:
            return False
    return _keyword_match(dog, f.keyword)


def filter_dogs(dogs: list[dict], f: BrowseFilter, today: date | None = None) -> list[dict]:
    today = today or date.today()
    return [dog for dog in dogs if matches(dog, f, today)]


def _ymd(dog: dict, field: str) -> str:
    return str(dog.get(field) or "")


def fit_results(dogs: list[dict], survey: Survey, today: date | None = None) -> dict[str, MatchResult]:
    """입양 매칭 설문으로 계산한 적합도 {구조번호: 결과}.

    둘러보기에서는 지역·품종을 화면의 조건으로 거르고 기준 위치가 없으므로,
    설문의 거리·품종 조건은 빼고 계산합니다. (거리 점수는 모두 중간값)
    """
    survey = replace(survey, max_km=None, breeds=())
    return {str(d.get("desertionNo")): score_dog(d, survey, None, today) for d in dogs}


def sort_dogs(
    dogs: list[dict], order: str = RECENT, today: date | None = None, fits: dict[str, MatchResult] | None = None
) -> list[dict]:
    """정렬 순서.

    - 최근 등록순: 공고 시작일이 최근인 아이부터
    - 공고 마감 임박순: 공고 중인 아이를 종료일이 가까운 순서로, 그다음 공고가 끝난 아이
    - 오래 기다린 순: 구조된 날이 오래된 아이부터
    - 나와 잘 맞는 순: 입양 매칭 설문 적합도가 높은 아이부터 (fits 필요, 같으면 최근 등록순)
    """
    today = today or date.today()
    if order == FIT and fits:
        recent = sort_dogs(dogs, RECENT, today)
        return sorted(recent, key=lambda d: -fits[str(d.get("desertionNo"))].score)
    if order == DEADLINE:
        return sorted(
            dogs,
            key=lambda d: (notice_status(d, today) != NOTICE, _ymd(d, "noticeEdt") or "99999999", _ymd(d, "desertionNo")),
        )
    if order == LONGEST:
        return sorted(dogs, key=lambda d: (_ymd(d, "happenDt") or "99999999", _ymd(d, "desertionNo")))
    return sorted(dogs, key=lambda d: (_ymd(d, "noticeSdt"), _ymd(d, "desertionNo")), reverse=True)
