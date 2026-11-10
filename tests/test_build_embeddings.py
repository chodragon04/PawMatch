# Copyright (c) 2026 Cho Yongjun
# SPDX-License-Identifier: MIT
"""scripts/build_embeddings.py 테스트: 이전 임베딩을 받지 못했을 때 처음부터 다시 만들지 않는지."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from pawmatch import data as D
from pawmatch import image_search as I

_spec = importlib.util.spec_from_file_location(
    "build_embeddings", Path(__file__).resolve().parent.parent / "scripts" / "build_embeddings.py"
)
build_embeddings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_embeddings)

DOGS = [{"desertionNo": "1", "popfile1": "https://example.com/1.jpg"}]


def run(monkeypatch, tmp_path, previous, *extra):
    snapshot = tmp_path / D.SNAPSHOT_FILE
    snapshot.write_bytes(D.encode_snapshot(DOGS, [], datetime.now(timezone.utc)))
    built = []

    def fake_build(dogs, prev, embedder, **kw):
        built.append(prev)
        index = I.PhotoIndex(np.array(["1"]), np.array(["u"]), np.ones((1, I.DIM), np.float32))
        return index, I.BuildStats()

    monkeypatch.setattr(build_embeddings, "read_remote_index", lambda: previous)
    monkeypatch.setattr(build_embeddings, "build_index", fake_build)
    monkeypatch.setattr(build_embeddings, "ClipEmbedder", lambda: None)
    out = tmp_path / "out"
    monkeypatch.setattr("sys.argv", ["build_embeddings.py", "--snapshot", str(snapshot), "--out", str(out), *extra])
    return build_embeddings.main(), (out / I.EMBEDDINGS_FILE).exists(), built


def test_missing_previous_embeddings_skip_instead_of_full_rebuild(monkeypatch, tmp_path):
    code, written, built = run(monkeypatch, tmp_path, None)
    assert code == 1 and not written and built == []  # 파일을 안 만들어야 워크플로가 이전 파일을 그대로 둠


def test_allow_fresh_builds_from_scratch(monkeypatch, tmp_path):
    code, written, built = run(monkeypatch, tmp_path, None, "--allow-fresh")
    assert code == 0 and written and built == [None]


def test_previous_embeddings_are_passed_on(monkeypatch, tmp_path):
    previous = I.empty_index()
    code, written, built = run(monkeypatch, tmp_path, previous)
    assert code == 0 and written and built == [previous]
