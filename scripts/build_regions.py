# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""구조동물 조회 API의 시/도·시/군/구 목록으로 지역 선택 목록(pawmatch/regions.json)을 만듭니다.

행정구역이 바뀌었을 때만 다시 실행하면 됩니다.

    python scripts/build_regions.py

API 목록에는 지역 선택에 맞지 않는 항목이 섞여 있어 정리합니다.
- 시/도 이름 자체(시/도청 직영), '가정보호', 이름 없는 항목
- 일반구(경기도 수원시 권선구 등): 시 단위로 고르면 충분합니다
- 폐지된 지역(연기군 → 2012년 세종특별자치시)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from pawmatch.api import BASE_URL, _items, _request  # noqa: E402
from pawmatch.regions import REGIONS_FILE  # noqa: E402

EXCLUDED = {"가정보호", "연기군"}


def clean_sigungu(sido: str, names: list[str | None]) -> list[str]:
    result: list[str] = []
    for name in names:
        if not name or name == sido or name in EXCLUDED or name in result:
            continue
        if sido.endswith("도") and name.endswith("구"):  # 도 아래의 '구'는 일반구
            continue
        result.append(name)
    return sorted(result)


def main() -> int:
    load_dotenv()
    api_key = os.getenv("DATA_GO_KR_API_KEY", "").strip()
    if not api_key:
        print("DATA_GO_KR_API_KEY 환경 변수가 없습니다.", file=sys.stderr)
        return 1

    sidos = _items(_request(f"{BASE_URL}/sido_v2", {"numOfRows": 100, "pageNo": 1}, api_key))
    regions: dict[str, list[str]] = {}
    for sido in sidos:
        name = sido["orgdownNm"]
        params = {"upr_cd": sido["orgCd"], "numOfRows": 500, "pageNo": 1}
        items = _items(_request(f"{BASE_URL}/sigungu_v2", params, api_key))
        regions[name] = clean_sigungu(name, [i.get("orgdownNm") for i in items])

    REGIONS_FILE.write_text(json.dumps(regions, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"시/도 {len(regions)}곳, 시/군/구 {sum(map(len, regions.values()))}곳 → {REGIONS_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
