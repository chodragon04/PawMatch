"""보호견·보호소 데이터를 불러옵니다.

공공데이터 API는 한 번 요청에 2~9초가 걸리고 가끔 연결이 끊겨서, GitHub Actions가 1시간마다
데이터를 받아 `data` 브랜치에 스냅샷 파일로 저장해 둡니다(.github/workflows/update-data.yml).
앱은 아래 순서로 데이터를 찾습니다.

1. 로컬 스냅샷 (data/snapshot/snapshot.json.gz, `python scripts/fetch_data.py`로 생성)
2. GitHub `data` 브랜치의 스냅샷
3. 스냅샷이 없거나 오래됐으면(3시간 초과) 공공데이터 API 직접 호출
4. API도 실패하면 오래된 스냅샷이라도 사용
"""

from __future__ import annotations

import gzip
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from pawmatch.api import ApiError, fetch_all_dogs, fetch_shelters

SNAPSHOT_FILE = "snapshot.json.gz"
LOCAL_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshot"
REMOTE_SNAPSHOT_URL = os.getenv(
    "PAWMATCH_SNAPSHOT_URL", "https://raw.githubusercontent.com/chodragon04/PawMatch/data"
)
MAX_SNAPSHOT_AGE = timedelta(hours=3)
MIN_DOGS = 100  # 이보다 적으면 API가 잘못된 응답을 준 것으로 보고 스냅샷을 저장하지 않습니다

# 화면에 쓰지 않는 개인 정보는 스냅샷에 저장하지 않습니다.
DROP_FIELDS = ("careOwnerNm", "rfidCd")

SNAPSHOT, API, STALE_SNAPSHOT = "snapshot", "api", "stale_snapshot"


@dataclass
class Dataset:
    dogs: list[dict]
    shelters: list[dict]
    fetched_at: datetime  # UTC
    source: str  # SNAPSHOT / API / STALE_SNAPSHOT

    def age(self, now: datetime | None = None) -> timedelta:
        return (now or datetime.now(timezone.utc)) - self.fetched_at


def _slim(dogs: list[dict]) -> list[dict]:
    return [{k: v for k, v in d.items() if k not in DROP_FIELDS} for d in dogs]


def encode_snapshot(dogs: list[dict], shelters: list[dict], fetched_at: datetime) -> bytes:
    payload = {
        "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "dogs": _slim(dogs),
        "shelters": shelters,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return gzip.compress(raw, mtime=0)


def decode_snapshot(blob: bytes, source: str = SNAPSHOT) -> Dataset:
    payload = json.loads(gzip.decompress(blob).decode("utf-8"))
    fetched_at = datetime.fromisoformat(payload["fetched_at"])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return Dataset(payload["dogs"], payload["shelters"], fetched_at, source)


def write_snapshot(directory: Path, dogs: list[dict], shelters: list[dict], fetched_at: datetime) -> Path:
    if len(dogs) < MIN_DOGS:
        raise ApiError(f"유기견이 {len(dogs)}마리뿐이라 스냅샷을 저장하지 않았습니다.")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / SNAPSHOT_FILE
    path.write_bytes(encode_snapshot(dogs, shelters, fetched_at))
    return path


def read_local_snapshot(directory: Path | None = None) -> Dataset | None:
    try:
        return decode_snapshot(((directory or LOCAL_SNAPSHOT_DIR) / SNAPSHOT_FILE).read_bytes())
    except (OSError, ValueError, KeyError):
        return None


def read_remote_snapshot(base_url: str | None = None, timeout: float = 15) -> Dataset | None:
    try:
        resp = requests.get(f"{(base_url or REMOTE_SNAPSHOT_URL).rstrip('/')}/{SNAPSHOT_FILE}", timeout=timeout)
        resp.raise_for_status()
        return decode_snapshot(resp.content)
    except (requests.RequestException, OSError, ValueError, KeyError):
        return None


def fetch_live(api_key: str) -> Dataset:
    """공공데이터 API에서 유기견과 보호소를 동시에 받아옵니다."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        dogs_future = pool.submit(fetch_all_dogs, api_key)
        shelters_future = pool.submit(fetch_shelters, api_key)
        dogs = dogs_future.result()
        shelters = shelters_future.result()
    return Dataset(_slim(dogs), shelters, datetime.now(timezone.utc), API)


def load_dataset(api_key: str | None, now: datetime | None = None) -> Dataset:
    """스냅샷 → API 순서로 데이터를 불러옵니다. 모두 실패하면 ApiError."""
    now = now or datetime.now(timezone.utc)
    newest: Dataset | None = None
    for read in (read_local_snapshot, read_remote_snapshot):
        snapshot = read()
        if snapshot is None:
            continue
        if snapshot.age(now) <= MAX_SNAPSHOT_AGE:
            return snapshot
        if newest is None or snapshot.fetched_at > newest.fetched_at:
            newest = snapshot

    error: ApiError | None = None
    if api_key:
        try:
            return fetch_live(api_key)
        except ApiError as exc:
            error = exc
    if newest is not None:
        newest.source = STALE_SNAPSHOT
        return newest
    raise error or ApiError("저장된 데이터가 없고 API 키도 설정되지 않았습니다.")
