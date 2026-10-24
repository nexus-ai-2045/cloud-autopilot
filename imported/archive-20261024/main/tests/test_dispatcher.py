import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dispatcher import Dispatcher


def _write_job(dirpath: Path, name: str, runner: str = "local", fallback=None) -> Path:
    manifest = {
        "name": name,
        "runner": runner,
        "identity": {"local": "local", "kaggle": "ainexus2045"}.get(runner, "local"),
        "entrypoint": "kernel",
    }
    if fallback:
        manifest["fallback"] = fallback
    path = dirpath / f"{name}.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_queue_runs_and_persists(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-a")
    calls = []

    def fake_local(job, base):
        calls.append(job.name)
        return 0

    d = Dispatcher({"local": fake_local}, tmp_path)
    assert d.run_queue(q) == {"job-a": "finished"}
    # 自動再開: 2 回目は終端済みスキップで runner を呼ばない
    d2 = Dispatcher({"local": fake_local}, tmp_path)
    assert d2.run_queue(q) == {"job-a": "finished"}
    assert calls == ["job-a"]


def test_fallback_to_local_on_failure(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-b", runner="kaggle", fallback=["local"])

    def failing_kaggle(job, base):
        raise RuntimeError("kaggle 死亡")

    def ok_local(job, base):
        return 0

    d = Dispatcher({"kaggle": failing_kaggle, "local": ok_local}, tmp_path)
    assert d.run_queue(q) == {"job-b": "finished"}
    events = [e["event"] for e in d.ledger.read("runs.jsonl")]
    assert "failed" in events and events[-1] == "finished"


def test_invalid_manifest_rejected(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    (q / "bad.json").write_text(json.dumps({"name": "bad", "runner": "kaggle", "entrypoint": "k"}), encoding="utf-8")
    d = Dispatcher({}, tmp_path)
    assert d.run_queue(q) == {"bad": "rejected"}


def test_all_runners_exhausted(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-c", runner="local")

    def bad_local(job, base):
        return 1

    d = Dispatcher({"local": bad_local}, tmp_path)
    assert d.run_queue(q) == {"job-c": "failed"}
    assert d.state.get("job-c") == "failed"
