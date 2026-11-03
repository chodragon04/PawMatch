"""공공데이터 API에서 보호견·보호소 데이터를 받아 스냅샷 파일로 저장합니다.

GitHub Actions(.github/workflows/update-data.yml)가 1시간마다 실행하고, 로컬에서도 쓸 수 있습니다.

    python scripts/fetch_data.py                 # data/snapshot/snapshot.json.gz
    python scripts/fetch_data.py --out some/dir  # 다른 폴더에 저장

API 키는 환경 변수 또는 .env의 DATA_GO_KR_API_KEY에서 읽습니다.
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
from pawmatch.data import LOCAL_SNAPSHOT_DIR, fetch_live, write_snapshot  # noqa: E402

API_KEY_ENV = "DATA_GO_KR_API_KEY"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=LOCAL_SNAPSHOT_DIR, help="저장할 폴더")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv(API_KEY_ENV, "").strip()
    if not api_key:
        print(f"{API_KEY_ENV} 환경 변수가 없습니다.", file=sys.stderr)
        return 1

    started = time.perf_counter()
    try:
        data = fetch_live(api_key)
        path = write_snapshot(args.out, data.dogs, data.shelters, data.fetched_at)
    except ApiError as exc:
        print(f"데이터를 받지 못했습니다: {exc}", file=sys.stderr)
        return 1

    print(
        f"유기견 {len(data.dogs):,}마리, 보호소 {len(data.shelters):,}곳 → {path} "
        f"({path.stat().st_size / 1024:,.0f}KB, {time.perf_counter() - started:.1f}초)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
