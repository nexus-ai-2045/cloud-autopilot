import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.api_client import RETRYABLE_STATUSES, TransientError, backoff_schedule, call_with_backoff
from core.ledger import Ledger
from core.manifest import JobManifest, ManifestError


def test_manifest_valid():
    m = JobManifest.from_dict(
        {"name": "j", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "kernel", "gpu": True}
    )
    assert m.gpu is True
    assert m.identity == "kaggle-main"


def test_manifest_missing_identity():
    with pytest.raises(ManifestError, match="必須フィールド"):
        JobManifest.from_dict({"name": "j", "runner": "kaggle", "entrypoint": "kernel"})


def test_manifest_unknown_runner():
    with pytest.raises(ManifestError, match="未知の runner"):
        JobManifest.from_dict({"name": "j", "runner": "aws", "identity": "x", "entrypoint": "x"})


def test_manifest_gcloud_is_out_of_scope():
    """この repo の実行環境は kaggle / colab / local のみ (責務境界)。"""
    with pytest.raises(ManifestError, match="未知の runner"):
        JobManifest.from_dict({"name": "j", "runner": "gcloud", "identity": "x", "entrypoint": "x"})


def test_manifest_fallback_local_only():
    with pytest.raises(ManifestError, match="fallback"):
        JobManifest.from_dict(
            {"name": "j", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "k", "fallback": ["colab"]}
        )


def test_backoff_schedule():
    assert backoff_schedule() == [5.0, 10.0, 20.0]


def test_backoff_retries_429_and_records(tmp_path):
    ledger = Ledger(tmp_path)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError(429)
        return "ok"

    slept = []
    assert call_with_backoff(flaky, api_name="t", ledger=ledger, sleep=slept.append) == "ok"
    assert slept == [5.0, 10.0]
    events = ledger.read("rate_limit.jsonl")
    assert [e["status"] for e in events] == [429, 429]


def test_backoff_gives_up_after_max(tmp_path):
    ledger = Ledger(tmp_path)

    def always_429():
        raise TransientError(429)

    with pytest.raises(TransientError):
        call_with_backoff(always_429, api_name="t", ledger=ledger, sleep=lambda _: None)
    assert len(ledger.read("rate_limit.jsonl")) == 4  # 初回 + 3 retry


def test_non_retryable_raises_immediately(tmp_path):
    ledger = Ledger(tmp_path)
    calls = {"n": 0}

    def bad_request():
        calls["n"] += 1
        raise TransientError(400)

    with pytest.raises(TransientError):
        call_with_backoff(bad_request, api_name="t", ledger=ledger, sleep=lambda _: None)
    assert calls["n"] == 1
    assert ledger.read("rate_limit.jsonl") == []


def test_retryable_statuses_contract():
    assert RETRYABLE_STATUSES == {429, 500, 502, 503, 504}


def test_ledger_run_roundtrip(tmp_path):
    ledger = Ledger(tmp_path)
    ledger.record_run("j", "kaggle", "kaggle-main", "started")
    ledger.record_run("j", "kaggle", "kaggle-main", "finished")
    events = ledger.read("runs.jsonl")
    assert [e["event"] for e in events] == ["started", "finished"]
    assert all(e["identity"] == "kaggle-main" for e in events)
