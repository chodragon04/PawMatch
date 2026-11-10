# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""pawmatch.data 단위 테스트 (스냅샷 읽기/쓰기, 불러오는 순서)."""

from datetime import datetime, timedelta, timezone

import pytest

from pawmatch import data as D
from pawmatch.api import ApiError

NOW = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
DOGS = [{"desertionNo": str(i), "careOwnerNm": "홍길동", "rfidCd": "410"} for i in range(D.MIN_DOGS)]
SHELTERS = [{"careNm": "A", "lat": "37.5", "lng": "127.0"}]


def test_snapshot_roundtrip_drops_personal_fields(tmp_path):
    D.write_snapshot(tmp_path, DOGS, SHELTERS, NOW)
    loaded = D.read_local_snapshot(tmp_path)
    assert loaded.fetched_at == NOW and loaded.shelters == SHELTERS
    assert len(loaded.dogs) == len(DOGS)
    assert "careOwnerNm" not in loaded.dogs[0] and "rfidCd" not in loaded.dogs[0]


def test_too_few_dogs_are_not_saved(tmp_path):
    with pytest.raises(ApiError):
        D.write_snapshot(tmp_path, DOGS[:3], SHELTERS, NOW)
    assert D.read_local_snapshot(tmp_path) is None


def test_fetch_live_rejects_too_few_dogs(monkeypatch):
    """API가 성공 코드와 함께 몇 마리만 주면, 앱의 정상 데이터를 덮어쓰지 않도록 실패로 봅니다."""
    monkeypatch.setattr(D, "fetch_shelters", lambda key: SHELTERS)
    monkeypatch.setattr(D, "fetch_all_dogs", lambda key: DOGS[:3])
    with pytest.raises(ApiError, match="3마리"):
        D.fetch_live("KEY")
    monkeypatch.setattr(D, "fetch_all_dogs", lambda key: DOGS)
    assert len(D.fetch_live("KEY").dogs) == len(DOGS)


def test_broken_snapshot_is_ignored(tmp_path):
    (tmp_path / D.SNAPSHOT_FILE).write_bytes(b"not gzip")
    assert D.read_local_snapshot(tmp_path) is None


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class Sources:
    """DataStore에 넣을 가짜 읽기 함수들. 뒤에서 하는 작업은 바로(동기로) 실행해 결과를 확인합니다."""

    def __init__(self):
        self.local = self.remote = self.live = None
        self.calls = {"remote": 0, "live": 0}
        self.background: list = []
        self.clock = Clock(NOW)

    def read_remote(self):
        self.calls["remote"] += 1
        return self.remote

    def fetch(self, key):
        self.calls["live"] += 1
        if isinstance(self.live, Exception):
            raise self.live
        return self.live

    def store(self, run_now=True):
        run = (lambda job: job()) if run_now else self.background.append
        return D.DataStore(lambda: self.local, self.read_remote, self.fetch, run, self.clock)


def at(minutes_old, source=D.SNAPSHOT):
    return D.Dataset([{"desertionNo": "s"}], SHELTERS, NOW - timedelta(minutes=minutes_old), source)


def test_fresh_snapshot_is_used_without_calling_api():
    src = Sources()
    src.remote = at(10)
    assert src.store().get("KEY") is src.remote
    assert src.calls["live"] == 0


def test_old_snapshot_is_shown_immediately_and_refreshed_in_background():
    src = Sources()
    src.remote = at(8 * 60)  # GitHub 예약 실행이 8시간 밀린 상황
    src.live = at(0, D.API)
    store = src.store(run_now=False)
    first = store.get("KEY")
    assert first is src.remote  # API를 기다리지 않고 바로 보여줌
    assert store.refreshing and len(src.background) == 1
    src.background.pop()()  # 뒤에서 하던 작업이 끝남
    assert store.get("KEY") is src.live and not store.refreshing


def test_newer_snapshot_found_in_background_skips_api():
    src = Sources()
    src.remote = at(8 * 60)
    store = src.store(run_now=False)
    store.get("KEY")
    src.remote = at(5)  # 그사이 GitHub Actions가 새 스냅샷을 만듦
    src.background.pop()()
    assert store.get("KEY") is src.remote and src.calls["live"] == 0


def test_background_failure_keeps_current_data_and_waits_before_retry():
    src = Sources()
    src.remote = at(8 * 60)
    src.live = ApiError("down")
    store = src.store()
    assert store.get("KEY") is src.remote
    assert store.last_error == "down" and src.calls["live"] == 1
    store.get("KEY")  # 바로 다시 와도 RECHECK_EVERY 동안은 재시도하지 않음
    assert src.calls["live"] == 1
    src.clock.now = NOW + D.RECHECK_EVERY + timedelta(seconds=1)
    store.get("KEY")
    assert src.calls["live"] == 2


def test_only_one_background_refresh_at_a_time():
    src = Sources()
    src.remote = at(8 * 60)
    store = src.store(run_now=False)
    store.get("KEY")
    src.clock.now = NOW + timedelta(hours=1)
    store.get("KEY")
    assert len(src.background) == 1


def test_without_api_key_old_snapshot_is_still_used():
    src = Sources()
    src.remote = at(8 * 60)
    assert src.store().get(None) is src.remote
    assert src.calls["live"] == 0


def test_no_snapshot_waits_for_api_or_raises():
    src = Sources()
    src.live = at(0, D.API)
    assert src.store().get("KEY") is src.live
    with pytest.raises(ApiError):
        Sources().store().get(None)
    failing = Sources()
    failing.live = ApiError("down")
    with pytest.raises(ApiError, match="down"):
        failing.store().get("KEY")


def test_newest_of_local_and_remote_is_used():
    src = Sources()
    src.local, src.remote = at(30), at(10)
    assert src.store().get("KEY") is src.remote
