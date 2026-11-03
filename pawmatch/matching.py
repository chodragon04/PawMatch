"""설문(주거 환경, 산책 시간 등)과 보호견 정보로 적합도 점수를 계산합니다.

항목별 점수(0~1)에 비중을 곱해 100점 만점으로 합칩니다.

| 항목       | 비중 | 근거 데이터                                   |
|------------|------|-----------------------------------------------|
| 크기       | 25   | 체중(어린 강아지는 품종), 주거 형태            |
| 활동량     | 20   | 나이·품종·특징 메모로 추정한 활동량, 산책 시간 |
| 성격       | 20   | 특징 메모 키워드, 반려 경험·가족 구성          |
| 돌봄 시간  | 15   | 나이, 집을 비우는 시간                         |
| 거리       | 15   | 보호소 좌표와 기준 위치 사이 거리              |
| 선호       | 5    | 선호 크기·나이·성별, 치료가 필요한 아이 여부   |

정보가 없는 항목(성격 메모 없음, 체중 오입력, 보호소 좌표 없음)은 감점하지 않고 0.5점(중립)으로 둡니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from pawmatch import traits as T

# ---------------------------------------------------------------- 설문

APARTMENT, HOUSE, YARD = "apartment", "house", "yard"
HOME_LABELS = {APARTMENT: "아파트·빌라", HOUSE: "단독주택 (마당 없음)", YARD: "마당 있는 주택"}

WALK_SHORT, WALK_MID, WALK_LONG = "short", "mid", "long"
WALK_LABELS = {WALK_SHORT: "30분 미만", WALK_MID: "30분 ~ 1시간", WALK_LONG: "1시간 이상"}

AWAY_SHORT, AWAY_MID, AWAY_LONG = "short", "mid", "long"
AWAY_LABELS = {AWAY_SHORT: "4시간 미만", AWAY_MID: "4 ~ 8시간", AWAY_LONG: "8시간 이상"}

ANY = "any"
SEX_PREF_LABELS = {ANY: "상관없음", "M": "수컷", "F": "암컷"}

WEIGHTS = {"size": 25, "activity": 20, "temperament": 20, "care": 15, "distance": 15, "preference": 5}
NEUTRAL = 0.5


@dataclass(frozen=True)
class Survey:
    home: str = APARTMENT
    walk: str = WALK_MID
    first_dog: bool = True
    has_kids: bool = False
    has_pets: bool = False
    away: str = AWAY_MID
    max_km: float | None = None  # None이면 거리 제한 없음
    pref_size: str = ANY  # traits.SMALL / MEDIUM / LARGE / ANY
    pref_age: str = ANY  # traits.PUPPY / YOUNG / ADULT / SENIOR / ANY
    pref_sex: str = ANY  # "M" / "F" / ANY
    health_ok: bool = False  # 치료가 필요한 아이도 괜찮은지


@dataclass
class MatchResult:
    dog: dict
    score: int  # 0~100
    parts: dict[str, float]  # 항목별 점수 0~1
    reasons: list[str] = field(default_factory=list)  # 잘 맞는 이유
    cautions: list[str] = field(default_factory=list)  # 미리 알아두면 좋은 점
    distance_km: float | None = None


# ---------------------------------------------------------------- 항목별 점수

# 주거 형태별 크기 적합도
_SIZE_FIT = {
    APARTMENT: {T.SMALL: 1.0, T.MEDIUM: 0.6, T.LARGE: 0.2},
    HOUSE: {T.SMALL: 0.9, T.MEDIUM: 0.9, T.LARGE: 0.6},
    YARD: {T.SMALL: 0.8, T.MEDIUM: 1.0, T.LARGE: 1.0},
}


def _size_text(p: T.DogProfile) -> str:
    label = T.SIZE_LABELS.get(p.size or "", "")
    return f"{label}견({p.weight:g}kg)" if p.weight is not None and p.age_group != T.PUPPY else f"{label}견"


def score_size(p: T.DogProfile, s: Survey, r: MatchResult) -> float:
    if p.size is None:
        if p.size_uncertain:
            r.cautions.append("어린 믹스견이라 다 자랐을 때 크기를 알기 어려워요")
        return NEUTRAL
    score = _SIZE_FIT[s.home][p.size]
    if score >= 0.9:
        r.reasons.append(f"{HOME_LABELS[s.home]}에서 지내기 좋은 {_size_text(p)}")
    elif score <= 0.6:
        r.cautions.append(f"{HOME_LABELS[s.home]}에서는 공간이 좁게 느껴질 수 있는 {_size_text(p)}")
    return score


_WALK_LEVEL = {WALK_SHORT: T.LOW, WALK_MID: T.MID, WALK_LONG: T.HIGH}


def score_activity(p: T.DogProfile, s: Survey, r: MatchResult) -> float:
    diff = p.energy - _WALK_LEVEL[s.walk]
    if diff <= 0:  # 아이보다 산책을 많이 해줄 수 있으면 큰 문제가 없습니다
        score = 1.0 - 0.2 * -diff
    else:  # 활동량이 많은 아이에게 산책이 부족하면 스트레스를 받기 쉽습니다
        score = 1.0 - 0.45 * diff
    if diff == 0:
        r.reasons.append(f"산책 시간({WALK_LABELS[s.walk]})과 활동량({T.ENERGY_LABELS[p.energy]})이 잘 맞아요")
    elif diff > 0:
        r.cautions.append(f"활동량이 많은 편이라 산책 시간({WALK_LABELS[s.walk]})이 부족할 수 있어요")
    return score


def score_temperament(p: T.DogProfile, s: Survey, r: MatchResult) -> float:
    memo = p.memo
    score = NEUTRAL
    quotes = []
    for flag in (T.GENTLE, T.FRIENDLY):
        if memo.has(flag):
            score += 0.25
            if memo.matches[flag] not in quotes:
                quotes.append(memo.matches[flag])
    if quotes:
        r.reasons.append("보호소 메모: " + ", ".join(f"'{q}'" for q in quotes))
    if memo.has(T.AGGRESSIVE):
        score -= 0.4
        if s.has_kids or s.first_dog or s.has_pets:
            score -= 0.3
        r.cautions.append(f"보호소 메모: '{memo.matches[T.AGGRESSIVE]}'. 성격을 꼭 문의해 보세요")
    if memo.has(T.TIMID):
        score -= 0.2 if s.first_dog else 0.0
        score -= 0.1 if s.has_kids else 0.0
        if s.first_dog or s.has_kids:
            r.cautions.append("겁이 많은 편이라 적응할 시간이 필요해요")
    return max(0.0, min(1.0, score))


# 집을 비우는 시간별 나이 적합도: 어린 강아지일수록 오래 혼자 두기 어렵습니다.
_CARE_FIT = {
    AWAY_SHORT: {"newborn": 1.0, T.PUPPY: 1.0, T.YOUNG: 1.0, T.ADULT: 1.0, T.SENIOR: 1.0},
    AWAY_MID: {"newborn": 0.5, T.PUPPY: 0.7, T.YOUNG: 0.9, T.ADULT: 1.0, T.SENIOR: 1.0},
    AWAY_LONG: {"newborn": 0.1, T.PUPPY: 0.4, T.YOUNG: 0.7, T.ADULT: 0.8, T.SENIOR: 0.9},
}


def score_care(p: T.DogProfile, s: Survey, r: MatchResult) -> float:
    if p.age_group is None:
        return NEUTRAL
    key = "newborn" if p.newborn else p.age_group
    score = _CARE_FIT[s.away][key]
    if score <= 0.5:
        r.cautions.append(f"어린 강아지라 혼자 있는 시간({AWAY_LABELS[s.away]})이 길면 힘들어해요")
    elif s.away != AWAY_SHORT and p.age_group in (T.ADULT, T.SENIOR):
        r.reasons.append("다 자란 아이라 혼자 있는 시간에도 비교적 잘 적응해요")
    return score


DEFAULT_DISTANCE_SCALE_KM = 50.0


def score_distance(distance_km: float | None, s: Survey, r: MatchResult) -> float:
    if distance_km is None:
        return NEUTRAL
    if s.max_km:
        score = 1.0 - 0.7 * min(distance_km / s.max_km, 1.0)  # 최대 거리에서 0.3점
    else:
        score = 1.0 / (1.0 + distance_km / DEFAULT_DISTANCE_SCALE_KM)  # 50km에서 0.5점
    if distance_km <= 20:
        r.reasons.append(f"가까운 보호소에 있어요 ({distance_km:.1f}km)")
    return score


def score_preference(dog: dict, p: T.DogProfile, s: Survey, r: MatchResult) -> float:
    checks = []
    if s.pref_size != ANY:
        checks.append(p.size == s.pref_size if p.size else None)
    if s.pref_age != ANY:
        checks.append(p.age_group == s.pref_age if p.age_group else None)
    if s.pref_sex != ANY:
        sex = (dog.get("sexCd") or "").upper()
        checks.append(sex == s.pref_sex if sex in ("M", "F") else None)
    if p.memo.has(T.HEALTH):
        if s.health_ok:
            r.reasons.append(f"보살핌이 필요할 수 있는 아이예요 ('{p.memo.matches[T.HEALTH]}')")
        else:
            checks.append(False)
            r.cautions.append(f"보호소 메모: '{p.memo.matches[T.HEALTH]}'. 건강 상태를 확인해 보세요")
    if not checks:
        return 1.0
    return sum(NEUTRAL if c is None else float(c) for c in checks) / len(checks)


# ---------------------------------------------------------------- 종합


def score_dog(
    dog: dict, survey: Survey, distance_km: float | None = None, today: date | None = None
) -> MatchResult:
    p = T.profile(dog, today)
    r = MatchResult(dog=dog, score=0, parts={}, distance_km=distance_km)
    r.parts = {
        "size": score_size(p, survey, r),
        "activity": score_activity(p, survey, r),
        "temperament": score_temperament(p, survey, r),
        "care": score_care(p, survey, r),
        "distance": score_distance(distance_km, survey, r),
        "preference": score_preference(dog, p, survey, r),
    }
    total = sum(WEIGHTS[k] * v for k, v in r.parts.items())
    r.score = round(total * 100 / sum(WEIGHTS.values()))
    return r


def rank_dogs(
    ranked: list[tuple[dict, float | None]],
    survey: Survey,
    limit: int | None = None,
    today: date | None = None,
) -> list[MatchResult]:
    """(유기견, 거리km) 목록을 점수가 높은 순으로 정렬합니다.

    최대 거리를 정했다면 그보다 먼 아이와 위치를 모르는 아이는 제외합니다.
    점수가 같으면 가까운 아이가 먼저 옵니다.
    """
    results = []
    for dog, distance in ranked:
        if survey.max_km and (distance is None or distance > survey.max_km):
            continue
        results.append(score_dog(dog, survey, distance, today))
    results.sort(key=lambda m: (-m.score, m.distance_km is None, m.distance_km or 0.0))
    return results[:limit] if limit else results
