"""보호견 사진 임베딩(embeddings.npz)을 만듭니다. GitHub Actions에서 데이터 스냅샷을 만든 뒤 실행합니다.

    python scripts/build_embeddings.py --snapshot out/snapshot.json.gz --out out

- 이전 임베딩(`data` 브랜치)에 있는 사진은 다시 계산하지 않습니다. 새로 들어온 아이의 사진만 계산합니다.
- --time-budget(초)이 지나면 남은 사진은 다음 실행으로 미룹니다. (처음 한 번은 사진이 많아 오래 걸림)
- 중간에 실패해도 이전 임베딩(지금 보호 중인 아이 것만)을 저장해서, 사진으로 찾기가 멈추지 않게 합니다.
- 이전 임베딩을 받지 못하면(일시적인 연결 오류 등) 처음부터 다시 만들지 않고 실패로 끝냅니다.
  처음부터 다시 만들면 30분 안에 다 못 끝내서 빠지는 아이가 생기기 때문입니다. 이때 워크플로는
  data 브랜치의 이전 embeddings.npz를 그대로 둡니다. 정말 처음 만들 때만 --allow-fresh를 붙입니다.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pawmatch.data import SNAPSHOT_FILE, decode_snapshot  # noqa: E402
from pawmatch.image_search import (  # noqa: E402
    EMBEDDINGS_FILE,
    ClipEmbedder,
    build_index,
    encode_index,
    keep_current,
    read_remote_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--snapshot", type=Path, default=Path("out") / SNAPSHOT_FILE)
    parser.add_argument("--out", type=Path, default=Path("out"))
    parser.add_argument("--time-budget", type=float, default=1500, help="사진 받기·계산에 쓸 최대 시간(초)")
    parser.add_argument("--workers", type=int, default=8, help="동시에 받을 사진 수")
    parser.add_argument("--allow-fresh", action="store_true", help="이전 임베딩이 없을 때 처음부터 만들기")
    args = parser.parse_args()

    started = time.monotonic()
    dogs = decode_snapshot(args.snapshot.read_bytes()).dogs
    previous = read_remote_index()
    print(f"보호견 {len(dogs):,}마리, 이전 임베딩 {len(previous) if previous else 0:,}장")
    if previous is None and not args.allow_fresh:
        print("이전 임베딩을 받지 못해 이번에는 건너뜁니다. (처음 만들 때는 --allow-fresh)", file=sys.stderr)
        return 1

    out_path = args.out / EMBEDDINGS_FILE
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        index, stats = build_index(
            dogs, previous, ClipEmbedder(), deadline=started + args.time_budget, workers=args.workers
        )
    except Exception as exc:  # 모델 내려받기 실패 등: 이전 임베딩이라도 남깁니다
        print(f"임베딩을 만들지 못했습니다: {type(exc).__name__}: {exc}", file=sys.stderr)
        if previous is None:
            return 1
        out_path.write_bytes(encode_index(keep_current(previous, dogs)))
        print("이전 임베딩을 그대로 저장했습니다.")
        return 1

    out_path.write_bytes(encode_index(index))
    print(
        f"사진 {len(index):,}장 ({len(index.dog_ids()):,}마리) → {out_path} ({out_path.stat().st_size / 1024:,.0f}KB, "
        f"{time.monotonic() - started:.0f}초) / 재사용 {stats.reused:,}, 새로 계산 {stats.embedded:,}, "
        f"실패 {stats.failed:,}, 시간 부족으로 다음에 {stats.skipped_for_time:,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
