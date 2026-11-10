# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""지역 선택 목록: 시/도 → 시/군/구.

목록(regions.json)은 구조동물 조회 API의 시/도·시/군/구 조회 결과를 정리한 것입니다.
(scripts/build_regions.py로 다시 만들 수 있습니다)
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

REGIONS_FILE = Path(__file__).with_name("regions.json")


@lru_cache(maxsize=1)
def load_regions() -> dict[str, tuple[str, ...]]:
    """{시/도: (시/군/구, ...)}. 파일이 없거나 깨졌으면 빈 dict."""
    try:
        raw = json.loads(REGIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {sido: tuple(names) for sido, names in raw.items()}
