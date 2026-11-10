# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""공공데이터 API에서 보호견·보호소 데이터를 받아 스냅샷 파일로 저장합니다.

GitHub Actions(.github/workflows/update-data.yml)가 30분마다 실행하고, 로컬에서도 쓸 수 있습니다.

    python scripts/fetch_data.py                 # data/snapshot/snapshot.json.gz
    python scripts/fetch_data.py --out some/dir  # 다른 폴더에 저장

API 키는 환경 변수 또는 .env의 DATA_GO_KR_API_KEY에서 읽습니다.

공공데이터 API가 잠깐 응답하지 않는 경우가 있어서(예: 새벽 점검), 받기에 실패하면 1분 간격으로 다시 시도합니다.
그래도 실패했지만 `data` 브랜치에 저장된 데이터가 아직 충분히 새것이면(기본 12시간 이내) '건너뜀'으로 끝내서
GitHub 실패 알림이 가지 않게 합니다. 이때 워크플로는 updated=false를 받아 뒤 단계(임베딩·저장)를 건너뜁니다.
저장된 데이터가 12시간보다 오래됐으면(키 만료, 긴 장애 등) 실패로 끝냅니다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

from pawmatch.api import ApiError  # noqa: E402
from pawmatch.data import LOCAL_SNAPSHOT_DIR, fetch_live, read_remote_snapshot, write_snapshot  # noqa: E402

API_KEY_ENV = "DATA_GO_KR_API_KEY"


def set_output(name: str, value: str) -> None:
    """GitHub Actions 단계 출력값 (로컬에서는 아무것도 하지 않음)."""
    path = os.getenv("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def fetch_with_retries(api_key: str, retries: int, wait_s: float, sleep=time.sleep):
    """fetch_live를 retries번까지 다시 시도합니다. 끝내 실패하면 마지막 ApiError를 다시 냅니다."""
    for attempt in range(retries + 1):
        try:
            return fetch_live(api_key)
        except ApiError as exc:
            if attempt == retries:
                raise
            print(f"데이터 받기 실패({attempt + 1}번째), {wait_s:.0f}초 뒤 다시 시도합니다: {exc}", file=sys.stderr)
            sleep(wait_s)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=LOCAL_SNAPSHOT_DIR, help="저장할 폴더")
    parser.add_argument("--retries", type=int, default=2, help="실패했을 때 다시 시도할 횟수")
    parser.add_argument("--retry-wait", type=float, default=60, help="다시 시도하기 전 기다릴 시간(초)")
    parser.add_argument(
        "--stale-after-hours", type=float, default=12,
        help="끝내 실패했을 때, 저장된 데이터가 이 시간보다 새것이면 실패 대신 건너뜀으로 끝냄",
    )  # fmt: skip
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        print(f"{API_KEY_ENV} 환경 변수가 없습니다.", file=sys.stderr)
        return 1

    started = time.perf_counter()
    try:
        data = fetch_with_retries(api_key, args.retries, args.retry_wait)
        path = write_snapshot(args.out, data.dogs, data.shelters, data.fetched_at)
    except ApiError as exc:
        print(f"데이터를 받지 못했습니다: {exc}", file=sys.stderr)
        set_output("updated", "false")
        stored = read_remote_snapshot()
        if stored is not None and stored.age().total_seconds() <= args.stale_after_hours * 3600:
            hours = stored.age().total_seconds() / 3600
            print(f"::warning::공공데이터 API에 연결하지 못해 이번 갱신은 건너뜁니다. (저장된 데이터는 {hours:.1f}시간 전 것)")
            return 0
        print("저장된 데이터도 오래돼서 실패로 끝냅니다. API 키나 공공데이터포털 상태를 확인해 주세요.", file=sys.stderr)
        return 1

    set_output("updated", "true")

    print(
        f"유기견 {len(data.dogs):,}마리, 보호소 {len(data.shelters):,}곳 → {path} "
        f"({path.stat().st_size / 1024:,.0f}KB, {time.perf_counter() - started:.1f}초)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
