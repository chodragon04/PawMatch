"""보호견·보호소 데이터를 불러옵니다.

공공데이터 API는 한 번 요청에 2~9초가 걸리고 가끔 연결이 끊겨서, GitHub Actions가 30분마다
데이터를 받아 `data` 브랜치에 스냅샷 파일로 저장해 둡니다(.github/workflows/update-data.yml).
하지만 GitHub의 예약 실행은 몇 시간씩 밀리거나 건너뛰는 경우가 많아서(실제로 6시간 넘게 안 돈 적도 있음),
앱이 스스로도 데이터를 새로 받습니다. (DataStore)

1. 처음에는 로컬 스냅샷(data/snapshot/) 또는 `data` 브랜치 스냅샷 중 새 것을 **오래됐어도 바로** 보여줍니다.
   스냅샷이 하나도 없을 때만 API 응답을 기다립니다.
2. 데이터가 FRESH_FOR(40분)보다 오래됐으면, 화면은 그대로 두고 **뒤에서** 새 스냅샷을 확인하고
   그래도 오래됐으면 API에서 직접 받아 바꿔 끼웁니다. (RECHECK_EVERY(5분)에 한 번까지만 시도)
3. 받은 데이터는 서버 프로세스 안에서 모든 사용자가 같이 씁니다.
"""

from __future__ import annotations

import gzip
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import requests

from pawmatch.api import ApiError, fetch_all_dogs, fetch_shelters

SNAPSHOT_FILE = "snapshot.json.gz"
LOCAL_SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshot"
REMOTE_SNAPSHOT_URL = os.getenv(
    "PAWMATCH_SNAPSHOT_URL", "https://raw.githubusercontent.com/chodragon04/PawMatch/data"
)
FRESH_FOR = timedelta(minutes=40)  # 이보다 새 데이터면 새로 받지 않음 (스냅샷은 30분마다 만들어짐)
RECHECK_EVERY = timedelta(minutes=5)  # 뒤에서 새로 받기를 시도하는 최소 간격
WARN_AFTER = timedelta(hours=24)  # 이보다 오래된 데이터면 화면에 알림
MIN_DOGS = 100  # 이보다 적으면 API가 잘못된 응답을 준 것으로 보고 스냅샷을 저장하지 않습니다

# 화면에 쓰지 않는 개인 정보는 스냅샷에 저장하지 않습니다.
DROP_FIELDS = ("careOwnerNm", "rfidCd")

SNAPSHOT, API = "snapshot", "api"


@dataclass
class Dataset:
    dogs: list[dict]
    shelters: list[dict]
    fetched_at: datetime  # UTC
    source: str  # SNAPSHOT / API

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
    """공공데이터 API에서 유기견과 보호소를 동시에 받아옵니다.

    API가 '성공'이라고 하면서 몇 마리만 주는 경우가 있어서, MIN_DOGS보다 적으면 실패로 봅니다.
    (앱이 뒤에서 새로 받을 때 정상 데이터를 덮어쓰지 않고, 스크립트는 다시 시도하게 됩니다)
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        dogs_future = pool.submit(fetch_all_dogs, api_key)
        shelters_future = pool.submit(fetch_shelters, api_key)
        dogs = dogs_future.result()
        shelters = shelters_future.result()
    if len(dogs) < MIN_DOGS:
        raise ApiError(f"유기견이 {len(dogs)}마리뿐이라 API 응답이 잘못된 것으로 보고 쓰지 않았습니다.")
    return Dataset(_slim(dogs), shelters, datetime.now(timezone.utc), API)


def _newer(a: Dataset | None, b: Dataset | None) -> Dataset | None:
    if a is None or b is None:
        return a or b
    return b if b.fetched_at > a.fetched_at else a


def _start_thread(target: Callable[[], None]) -> None:
    threading.Thread(target=target, name="pawmatch-data-refresh", daemon=True).start()


class DataStore:
    """서버 프로세스 하나에서 같이 쓰는 데이터 보관소. 오래된 데이터는 뒤에서 새로 받아 바꿉니다.

    읽기 함수와 스레드 실행 방법은 테스트에서 바꿔 끼울 수 있게 인자로 받습니다.
    """

    def __init__(
        self,
        read_local: Callable[[], Dataset | None] = lambda: read_local_snapshot(),
        read_remote: Callable[[], Dataset | None] = lambda: read_remote_snapshot(),
        fetch: Callable[[str], Dataset] = lambda key: fetch_live(key),
        run_in_background: Callable[[Callable[[], None]], None] = _start_thread,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._read_local, self._read_remote, self._fetch = read_local, read_remote, fetch
        self._run_in_background, self._clock = run_in_background, clock
        self._lock = threading.Lock()
        self.dataset: Dataset | None = None
        self.refreshing = False
        self.last_attempt: datetime | None = None
        self.last_error: str | None = None

    def get(self, api_key: str | None) -> Dataset:
        """지금 가진 데이터를 바로 돌려줍니다. 오래됐으면 뒤에서 새로 받기 시작합니다."""
        with self._lock:
            current = self.dataset
        if current is None:
            current = self._first_load(api_key)
        self._maybe_refresh(api_key)
        with self._lock:
            return self.dataset or current

    def _first_load(self, api_key: str | None) -> Dataset:
        found = _newer(self._read_local(), self._read_remote())
        if found is None:  # 스냅샷이 하나도 없을 때만 API 응답을 기다립니다
            if not api_key:
                raise ApiError("저장된 데이터가 없고 API 키도 설정되지 않았습니다.")
            found = self._fetch(api_key)
            with self._lock:
                self.last_attempt = self._clock()
        with self._lock:
            self.dataset = _newer(self.dataset, found)
            return self.dataset  # type: ignore[return-value]

    def _maybe_refresh(self, api_key: str | None) -> None:
        now = self._clock()
        with self._lock:
            if self.refreshing or self.dataset is None or self.dataset.age(now) <= FRESH_FOR:
                return
            if self.last_attempt is not None and now - self.last_attempt < RECHECK_EVERY:
                return
            self.refreshing, self.last_attempt = True, now
        self._run_in_background(lambda: self._refresh(api_key))

    def _refresh(self, api_key: str | None) -> None:
        """새 스냅샷을 먼저 확인하고, 그래도 오래됐으면 API에서 직접 받습니다."""
        try:
            remote = self._read_remote()
            with self._lock:
                self.dataset = _newer(self.dataset, remote)
                still_old = self.dataset is None or self.dataset.age(self._clock()) > FRESH_FOR
            if still_old and api_key:
                live = self._fetch(api_key)
                with self._lock:
                    self.dataset = _newer(self.dataset, live)
            self.last_error = None
        except Exception as exc:  # 뒤에서 도는 작업이라 실패해도 지금 데이터를 계속 씁니다
            self.last_error = str(exc)
        finally:
            with self._lock:
                self.refreshing = False


STORE = DataStore()
