"""pawmatch.data 단위 테스트 (스냅샷 읽기/쓰기, 불러오는 순서)."""

from datetime import datetime, timedelta, timezone

import pytest

from pawmatch import data as D
from pawmatch.api import ApiError

NOW = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
DOGS = [{"desertionNo": str(i), "careOwnerNm": "홍길동", "rfidCd": "410"} for i in range(D.MIN_DOGS)]
SHELTERS = [{"careNm": "A", "lat": "37.5", "lng": "127.0"}]


LIMIT_H = D.MAX_SNAPSHOT_AGE.total_seconds() / 3600  # 최신으로 보는 기준(시간)


def make(age_hours, source=D.SNAPSHOT):
    return D.Dataset([{"desertionNo": "s"}], SHELTERS, NOW - timedelta(hours=age_hours), source)


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


def test_broken_snapshot_is_ignored(tmp_path):
    (tmp_path / D.SNAPSHOT_FILE).write_bytes(b"not gzip")
    assert D.read_local_snapshot(tmp_path) is None


@pytest.fixture
def sources(monkeypatch):
    state = {"local": None, "remote": None, "live": None, "live_calls": 0}

    def live(key):
        state["live_calls"] += 1
        if isinstance(state["live"], Exception):
            raise state["live"]
        return state["live"]

    monkeypatch.setattr(D, "read_local_snapshot", lambda: state["local"])
    monkeypatch.setattr(D, "read_remote_snapshot", lambda: state["remote"])
    monkeypatch.setattr(D, "fetch_live", live)
    return state


def test_fresh_snapshot_is_used_without_calling_api(sources):
    sources["remote"] = make(1)
    assert D.load_dataset("KEY", NOW) is sources["remote"]
    assert sources["live_calls"] == 0


def test_stale_snapshot_falls_back_to_api(sources):
    sources["remote"] = make(LIMIT_H + 1)
    sources["live"] = make(0, D.API)
    assert D.load_dataset("KEY", NOW).source == D.API


def test_api_failure_uses_newest_stale_snapshot(sources):
    sources["local"], sources["remote"] = make(LIMIT_H + 5), make(LIMIT_H + 1)
    sources["live"] = ApiError("down")
    result = D.load_dataset("KEY", NOW)
    assert result is sources["remote"] and result.source == D.STALE_SNAPSHOT


def test_works_without_api_key_when_snapshot_exists(sources):
    sources["remote"] = make(1)
    assert D.load_dataset(None, NOW).source == D.SNAPSHOT


def test_nothing_available_raises(sources):
    with pytest.raises(ApiError):
        D.load_dataset(None, NOW)
    sources["live"] = ApiError("down")
    with pytest.raises(ApiError, match="down"):
        D.load_dataset("KEY", NOW)


def test_snapshot_is_fresh_up_to_the_limit(sources):
    sources["remote"] = make(LIMIT_H - 0.5)  # 예약 실행이 몇 시간 밀려도 스냅샷을 씀
    assert D.load_dataset("KEY", NOW) is sources["remote"] and sources["live_calls"] == 0
