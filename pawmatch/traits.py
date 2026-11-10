# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""API 원문 값(체중, 나이, 품종, 특징 메모)에서 매칭·검색에 쓸 정보를 뽑아냅니다.

값이 잘못 입력되었거나 알 수 없으면 None을 돌려주고, 점수 계산에서는 '모름'으로 다룹니다.
분석 근거는 docs/data-analysis.md 참고.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from pawmatch.display import today_kst

# ---------------------------------------------------------------- 체중 / 크기

SMALL, MEDIUM, LARGE = "small", "medium", "large"
SIZE_LABELS = {SMALL: "소형", MEDIUM: "중형", LARGE: "대형"}
SMALL_MAX_KG = 10.0  # 10kg 미만: 소형
MEDIUM_MAX_KG = 25.0  # 10~25kg: 중형, 25kg 이상: 대형
MAX_VALID_KG = 100.0  # 이보다 무거우면 잘못 입력된 값으로 봅니다 (예: "2500(Kg)")

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def parse_weight(raw: str | None) -> float | None:
    """'5.6(Kg)' -> 5.6. '12..00', '6,3', '1.8~2.0'(평균) 같은 오입력도 최대한 읽습니다."""
    if not raw:
        return None
    text = re.sub(r"\.{2,}", ".", str(raw)).replace(",", ".")
    numbers = [float(n) for n in _NUMBER_RE.findall(text)]
    if not numbers:
        return None
    weight = sum(numbers[:2]) / len(numbers[:2]) if "~" in text else numbers[0]
    return weight if 0 < weight <= MAX_VALID_KG else None


def size_from_weight(weight: float | None) -> str | None:
    if weight is None:
        return None
    if weight < SMALL_MAX_KG:
        return SMALL
    return MEDIUM if weight < MEDIUM_MAX_KG else LARGE


# 어린 강아지는 지금 체중으로 다 자란 크기를 알 수 없어 품종으로 추정합니다.
_SMALL_BREEDS = (
    "말티즈", "푸들", "포메라니안", "치와와", "요크셔", "시츄", "시추", "비숑", "닥스훈트", "페키니즈",
    "파피용", "미니어쳐", "미니어처", "퍼그", "슈나우져", "슈나우저", "말티푸", "재패니즈 친", "토이",
)  # fmt: skip
_LARGE_BREEDS = (
    "리트리버", "허스키", "셰퍼드", "세퍼드", "도사", "풍산", "말라뮤트", "사모예드", "피레니즈",
    "로트와일러", "도베르만", "버니즈", "그레이하운드", "마스티프", "아키타", "말리노이즈",
)  # fmt: skip
_ACTIVE_BREEDS = (
    "보더 콜리", "보더콜리", "허스키", "진도", "풍산", "라이카", "리트리버", "셰퍼드", "세퍼드", "비글",
    "잭 러셀", "잭러셀", "코기", "말리노이즈", "달마시안", "시바", "스피츠", "말라뮤트", "포인터", "세터",
)  # fmt: skip


def _breed(dog: dict) -> str:
    return str(dog.get("kindNm") or dog.get("kindFullNm") or "")


def is_mixed(dog: dict) -> bool:
    breed = _breed(dog)
    return not breed or "믹스" in breed or breed.strip() in ("기타", "[개] 기타")


def breed_size(dog: dict) -> str | None:
    """품종으로 추정한 다 자란 크기. 믹스견이거나 목록에 없으면 None."""
    breed = _breed(dog)
    if any(b in breed for b in _LARGE_BREEDS):  # '도사 믹스견'처럼 큰 품종 믹스는 크게 자랍니다
        return LARGE
    if is_mixed(dog):
        return None
    if any(b in breed for b in _SMALL_BREEDS):
        return SMALL
    return None


def is_active_breed(dog: dict) -> bool:
    breed = _breed(dog)
    return any(b in breed for b in _ACTIVE_BREEDS)


# ---------------------------------------------------------------- 나이

PUPPY, YOUNG, ADULT, SENIOR = "puppy", "young", "adult", "senior"
AGE_LABELS = {PUPPY: "1살 미만", YOUNG: "1~2살", ADULT: "3~7살", SENIOR: "8살 이상"}

_BIRTH_YEAR_RE = re.compile(r"(\d{4})")


def birth_year(raw: str | None) -> int | None:
    m = _BIRTH_YEAR_RE.search(raw or "")
    return int(m.group(1)) if m else None


def age_years(raw: str | None, today: date | None = None) -> int | None:
    """출생연도만 있으므로 '올해 - 출생연도'로 계산합니다. (2026년생 → 0살)"""
    year = birth_year(raw)
    if year is None:
        return None
    age = (today or today_kst()).year - year
    return age if 0 <= age <= 30 else None


def is_newborn(raw: str | None) -> bool:
    """'2026(60일미만)(년생)'처럼 태어난 지 60일이 안 된 강아지."""
    return "60일" in (raw or "")


def age_group(raw: str | None, today: date | None = None) -> str | None:
    if is_newborn(raw):
        return PUPPY
    age = age_years(raw, today)
    if age is None:
        return None
    if age < 1:
        return PUPPY
    if age <= 2:
        return YOUNG
    return ADULT if age <= 7 else SENIOR


# ---------------------------------------------------------------- 특징 메모 (specialMark)

GENTLE, FRIENDLY, TIMID, AGGRESSIVE, ACTIVE, CALM, HEALTH = (
    "gentle", "friendly", "timid", "aggressive", "active", "calm", "health",
)  # fmt: skip

_KEYWORDS: dict[str, re.Pattern] = {
    GENTLE: re.compile(r"온순|순하|순함|순해|순둥|순딩|얌전|착하|착함|착해|착한"),
    FRIENDLY: re.compile(r"사람을?\s?(?:잘\s?)?(?:좋아|따[르름라])|친화|애교|사교|잘\s?따[르름라]|사람\s?좋아"),
    TIMID: re.compile(r"겁|소심|경계|예민|낯가림|낯을\s?가|무서워"),
    AGGRESSIVE: re.compile(r"사나|공격|입질|물어|무는|물려|물기|물음|으르렁"),
    ACTIVE: re.compile(r"활발|에너지|발랄|활동적|장난"),
    CALM: re.compile(r"얌전|조용|차분"),
    HEALTH: re.compile(
        r"피부|부상|절뚝|파행|골절|탈장|종양|질환|사상충|양성|외상|안구|백내장|실명|마비|심장|빈혈|"
        r"탈수|치료|진드기|곰팡이|상처|출혈|기침|설사|구토|염증|감염|수술|장애|불편|교통사고|의식"
    ),
}
# '입질 없음', '공격성 없음', '사납지 않음'처럼 바로 뒤에 부정하는 말이 오면 해당하지 않는 것으로 봅니다.
_NEGATION_RE = re.compile(r"^[^,.\s]{0,3}\s?(?:없|않|안\s?함|x\b|X\b|無)")
# '심장사상충 음성', '사상충&파보 음성'(검사 결과 음성), '심장사상충약'(예방약)은 건강 문제로 보지 않습니다.
_NEGATIVE_TEST_RE = re.compile(r"^[^,./]{0,8}(?:음성|예방)|^[^,./\s]{0,4}\s?약(?!간|하|해)")
_SEGMENT_SPLIT_RE = re.compile(r"[,./·\n]|\s{2,}")
SNIPPET_MAX = 24


def _snippet(text: str, start: int, end: int) -> str:
    """찾은 단어가 들어 있는 구절(쉼표·마침표 사이)을 돌려줍니다. 추천 이유에 그대로 인용합니다."""
    left = max((m.end() for m in _SEGMENT_SPLIT_RE.finditer(text, 0, start)), default=0)
    right_m = _SEGMENT_SPLIT_RE.search(text, end)
    segment = text[left : right_m.start() if right_m else len(text)].strip()
    return segment if len(segment) <= SNIPPET_MAX else segment[: SNIPPET_MAX - 1] + "…"


@dataclass(frozen=True)
class MemoTraits:
    """특징 메모에서 찾은 성격·건강 정보. matches에는 단어가 나온 구절을 남겨 추천 이유에 인용합니다."""

    flags: frozenset[str] = frozenset()
    matches: dict[str, str] = field(default_factory=dict)

    def has(self, flag: str) -> bool:
        return flag in self.flags


def memo_traits(memo: str | None) -> MemoTraits:
    text = memo or ""
    flags, matches = set(), {}
    for flag, pattern in _KEYWORDS.items():
        for m in pattern.finditer(text):
            rest = text[m.end() :]
            if flag == HEALTH and _NEGATIVE_TEST_RE.match(rest):
                continue
            if _NEGATION_RE.match(rest):
                if flag in (AGGRESSIVE, TIMID):  # '입질 없음'은 순하다는 뜻
                    flags.add(GENTLE)
                    matches.setdefault(GENTLE, _snippet(text, m.start(), m.end()))
                continue
            flags.add(flag)
            matches.setdefault(flag, _snippet(text, m.start(), m.end()))
            break
    return MemoTraits(frozenset(flags), matches)


# ---------------------------------------------------------------- 종합

LOW, MID, HIGH = 0, 1, 2
ENERGY_LABELS = {LOW: "차분한 편", MID: "보통", HIGH: "활발한 편"}


@dataclass(frozen=True)
class DogProfile:
    weight: float | None
    size: str | None  # 다 자랐을 때 예상 크기 (모르면 None)
    size_uncertain: bool  # 어린 믹스견처럼 다 자란 크기를 알기 어려운 경우
    age_group: str | None
    newborn: bool
    energy: int
    memo: MemoTraits


def energy_level(dog: dict, group: str | None, memo: MemoTraits) -> int:
    """나이, 품종, 특징 메모로 활동량을 추정합니다. (0 차분 ~ 2 활발)"""
    level = {PUPPY: HIGH, YOUNG: HIGH, ADULT: MID, SENIOR: LOW}.get(group or "", MID)
    if is_active_breed(dog):
        level += 1
    if memo.has(ACTIVE):
        level += 1
    if memo.has(CALM) and not memo.has(ACTIVE):
        level -= 1
    return max(LOW, min(HIGH, level))


def profile(dog: dict, today: date | None = None) -> DogProfile:
    weight = parse_weight(dog.get("weight"))
    group = age_group(dog.get("age"), today)
    current = size_from_weight(weight)
    size, uncertain = current, False
    if group == PUPPY:
        # 어린 강아지는 품종으로 추정하고, 믹스견이면 지금 이미 대형인 경우만 확정합니다.
        size = breed_size(dog) or (LARGE if current == LARGE else None)
        uncertain = size is None
    memo = memo_traits(dog.get("specialMark"))
    return DogProfile(
        weight=weight,
        size=size,
        size_uncertain=uncertain,
        age_group=group,
        newborn=is_newborn(dog.get("age")),
        energy=energy_level(dog, group, memo),
        memo=memo,
    )
