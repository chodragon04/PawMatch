# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""보호소 좌표 확인: 보호소 주소를 카카오 주소 검색으로 찾아 공공데이터의 좌표와 비교하고, 틀린 곳만 고칩니다.

    KAKAO_REST_API_KEY=... python scripts/check_shelter_coords.py               # pawmatch/shelter_coords.json 저장
    KAKAO_REST_API_KEY=... python scripts/check_shelter_coords.py --out x.json  # 다른 곳에 저장

- 데이터는 data 브랜치 스냅샷(보호소 목록)을 씁니다. 공공데이터 API 키는 필요 없습니다.
- 2026년 11월에 GitHub Actions에서 한 번 실행해 pawmatch/shelter_coords.json을 만들었습니다.
  (GitHub Actions에서 실행하면 결과 표가 실행 요약에 나옵니다)
- 보호소가 새로 생기거나 주소가 바뀌었을 때 다시 실행하면 됩니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pawmatch.data import read_remote_snapshot  # noqa: E402
from pawmatch.kakao import KakaoError, geocode_address, search_place  # noqa: E402
from pawmatch.shelter_coords import FIX_KM, FIXES_FILE, CheckResult, check_shelter, fixes_payload  # noqa: E402

KAKAO_KEY_ENV = "KAKAO_REST_API_KEY"
PAUSE_S = 0.05  # 카카오에 너무 빠르게 연달아 요청하지 않도록


def unique_shelters(shelters: list[dict]) -> list[dict]:
    """같은 보호소 번호가 여러 번 나오면 한 번만 확인합니다."""
    seen: dict[str, dict] = {}
    for s in shelters:
        seen.setdefault(str(s.get("careRegNo") or s.get("careNm") or len(seen)), s)
    return list(seen.values())


def report(results: list[CheckResult]) -> str:
    """결과 요약(마크다운): 고칠 곳, 못 찾은 곳, 전체 숫자."""
    fix = [r for r in results if r.needs_fix]
    missing = [r for r in results if r.kakao is None]
    headline = (
        f"보호소 {len(results)}곳 확인: 좌표가 {FIX_KM:g}km 넘게 다르거나 없어서 고칠 곳 **{len(fix)}곳**, "
        f"카카오에서 못 찾은 곳 {len(missing)}곳"
    )
    lines = [
        headline,
        "",
        "| 보호소 | 주소 | API 좌표 | 카카오 좌표 | 차이 | 카카오가 찾은 곳 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in sorted(fix, key=lambda r: -(r.diff_km or 1e9)):
        api = f"{r.api[0]:.4f}, {r.api[1]:.4f}" if r.api else "없음/한국 밖"
        diff = f"{r.diff_km:,.1f}km" if r.diff_km is not None else "-"
        lines.append(f"| {r.name} | {r.address} | {api} | {r.kakao[0]:.4f}, {r.kakao[1]:.4f} | {diff} | {r.found_as} |")
    if missing:
        lines += ["", "카카오에서 못 찾은 곳 (지금 좌표를 그대로 씀):", ""]
        lines += [f"- {r.name}: {r.address}" for r in missing]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=FIXES_FILE, help="결과 파일")
    parser.add_argument("--print-json", action="store_true", help="결과 파일 내용을 로그에도 출력")
    args = parser.parse_args()

    api_key = os.getenv(KAKAO_KEY_ENV, "").strip()
    if not api_key:
        print(f"{KAKAO_KEY_ENV} 환경 변수가 없습니다.", file=sys.stderr)
        return 1
    data = read_remote_snapshot()
    if data is None:
        print("data 브랜치의 스냅샷을 받지 못했습니다.", file=sys.stderr)
        return 1

    def geocode(query: str):
        time.sleep(PAUSE_S)
        return geocode_address(query, api_key)

    def place(query: str, must_contain: str):
        time.sleep(PAUSE_S)
        return search_place(query, must_contain, api_key)

    shelters = unique_shelters(data.shelters)
    try:
        results = [check_shelter(s, geocode, place) for s in shelters]
    except KakaoError as exc:  # 키 오류·사용량 초과: 일부 결과로 파일을 만들지 않습니다
        print(f"카카오 API 오류로 멈췄습니다: {exc}", file=sys.stderr)
        return 1

    payload = fixes_payload(results, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    summary = report(results)
    print(summary)
    print(f"\n→ {args.out} (고칠 곳 {len(payload['fixes'])}곳)")
    if args.print_json:
        print("\n----- shelter_coords.json -----")
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    step_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write("## 보호소 좌표 확인\n\n" + summary + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
