"""scripts/fetch_data.py 테스트: 공공데이터 API가 잠깐 응답하지 않을 때의 동작."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pawmatch import data as D
from pawmatch.api import ApiError

_spec = importlib.util.spec_from_file_location(
    "fetch_data", Path(__file__).resolve().parent.parent / "scripts" / "fetch_data.py"
)
fetch_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_data)

DOGS = [{"desertionNo": str(i)} for i in range(D.MIN_DOGS)]


def dataset(hours_old=0.0):
    return D.Dataset(DOGS, [], datetime.now(timezone.utc) - timedelta(hours=hours_old), D.SNAPSHOT)


@pytest.fixture
def run(monkeypatch, tmp_path):
    """fetch_data.main()을 가짜 API로 실행하고 (종료 코드, GitHub 출력, 저장 여부, 시도 횟수)를 돌려줍니다."""
    output = tmp_path / "github_output"

    def _run(results, stored=None):
        calls = []

        def fake_fetch(key):
            calls.append(key)
            r = results[min(len(calls) - 1, len(results) - 1)]
            if isinstance(r, Exception):
                raise r
            return r

        monkeypatch.setattr(fetch_data, "fetch_live", fake_fetch)
        monkeypatch.setattr(fetch_data, "read_remote_snapshot", lambda: stored)
        monkeypatch.setattr(fetch_data.time, "sleep", lambda s: None)
        monkeypatch.setenv("DATA_GO_KR_API_KEY", "KEY")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output))
        monkeypatch.setattr("sys.argv", ["fetch_data.py", "--out", str(tmp_path / "out"), "--retry-wait", "0"])
        code = fetch_data.main()
        saved = (tmp_path / "out" / D.SNAPSHOT_FILE).exists()
        return code, output.read_text() if output.exists() else "", saved, len(calls)

    return _run


def test_success_after_retry(run):
    code, out, saved, calls = run([ApiError("timeout"), dataset()])
    assert (code, saved, calls) == (0, True, 2)
    assert "updated=true" in out


def test_api_down_but_recent_data_is_skipped_not_failed(run):
    code, out, saved, calls = run([ApiError("timeout")], stored=dataset(hours_old=5))
    assert code == 0 and not saved and calls == 3  # 처음 + 다시 시도 2번
    assert "updated=false" in out  # 워크플로는 이 값으로 저장 단계를 건너뜀


def test_api_down_and_old_data_fails(run):
    code, out, saved, _ = run([ApiError("timeout")], stored=dataset(hours_old=13))
    assert code == 1 and not saved and "updated=false" in out


def test_api_down_and_no_stored_data_fails(run):
    code, _, saved, _ = run([ApiError("timeout")], stored=None)
    assert code == 1 and not saved
