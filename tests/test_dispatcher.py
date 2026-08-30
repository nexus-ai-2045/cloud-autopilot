import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import IdentityBook
from core.dispatcher import Dispatcher

# テスト用の名義帳。実アカウント名は一切使わない (repo 全体の方針)。
BOOK = IdentityBook.from_dict(
    {
        "identities": {
            "local": {"runner": "local", "account": "local"},
            "kaggle-main": {"runner": "kaggle", "account": "test-kaggle-user"},
        }
    }
)


def _write_job(dirpath: Path, name: str, runner: str = "local", fallback=None) -> Path:
    manifest = {
        "name": name,
        "runner": runner,
        "identity": {"local": "local", "kaggle": "kaggle-main"}.get(runner, "local"),
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

    def fake_local(job, base, ident):
        calls.append((job.name, ident.account))
        return 0

    d = Dispatcher({"local": fake_local}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"job-a": "finished"}
    # 自動再開: 2 回目は終端済みスキップで runner を呼ばない
    d2 = Dispatcher({"local": fake_local}, tmp_path, identities=BOOK)
    assert d2.run_queue(q) == {"job-a": "finished"}
    assert calls == [("job-a", "local")]


def test_fallback_to_local_on_failure(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-b", runner="kaggle", fallback=["local"])

    def failing_kaggle(job, base, ident):
        raise RuntimeError("kaggle 死亡")

    def ok_local(job, base, ident):
        return 0

    d = Dispatcher({"kaggle": failing_kaggle, "local": ok_local}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"job-b": "finished"}
    events = [e["event"] for e in d.ledger.read("runs.jsonl")]
    assert "failed" in events and events[-1] == "finished"


def test_invalid_manifest_rejected(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    (q / "bad.json").write_text(json.dumps({"name": "bad", "runner": "kaggle", "entrypoint": "k"}), encoding="utf-8")
    d = Dispatcher({}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"bad": "rejected"}


def test_unresolvable_identity_rejected_before_run(tmp_path):
    """config に無い名義のジョブは runner を呼ばずに rejected (fail-closed)。"""
    q = tmp_path / "queue"
    q.mkdir()
    (q / "ghost.json").write_text(
        json.dumps({"name": "ghost", "runner": "kaggle", "identity": "no-such-alias", "entrypoint": "k"}),
        encoding="utf-8",
    )
    calls = []

    def spy_kaggle(job, base, ident):
        calls.append(job.name)
        return 0

    d = Dispatcher({"kaggle": spy_kaggle}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"ghost": "rejected"}
    assert calls == []  # 名義が解決できないのに走ってはいけない
    events = d.ledger.read("runs.jsonl")
    assert events and events[-1]["event"] == "rejected"


def test_all_runners_exhausted(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-c", runner="local")

    def bad_local(job, base, ident):
        return 1

    d = Dispatcher({"local": bad_local}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"job-c": "failed"}
    assert d.state.get("job-c") == "failed"


def test_ledger_records_resolved_account(tmp_path):
    """台帳には alias と解決済み account の両方が残る (帰属の証跡)。"""
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-d", runner="kaggle")

    def ok_kaggle(job, base, ident):
        return 0

    d = Dispatcher({"kaggle": ok_kaggle}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"job-d": "finished"}
    finished = [e for e in d.ledger.read("runs.jsonl") if e["event"] == "finished"]
    assert finished[-1]["identity"] == "kaggle-main"
    assert finished[-1]["account"] == "test-kaggle-user"


def test_finished_not_clobbered_by_later_config_error(tmp_path):
    """finished 済みジョブは、後から名義設定が壊れても rejected に上書きされない。"""
    q = tmp_path / "queue"
    q.mkdir()
    _write_job(q, "job-e", runner="kaggle")
    d = Dispatcher({"kaggle": lambda j, b, i: 0}, tmp_path, identities=BOOK)
    assert d.run_queue(q) == {"job-e": "finished"}

    # 同じ job 名のまま、未登録エイリアスに書き換える (設定破壊を再現)
    (q / "job-e.json").write_text(
        json.dumps({"name": "job-e", "runner": "kaggle", "identity": "no-such", "entrypoint": "kernel"}),
        encoding="utf-8",
    )
    d2 = Dispatcher({"kaggle": lambda j, b, i: 0}, tmp_path, identities=BOOK)
    assert d2.run_queue(q) == {"job-e": "finished"}  # 終端維持 (再実行も上書きもしない)
    assert d2.state.get("job-e") == "finished"


def test_local_runner_with_relative_base_dir(tmp_path, monkeypatch):
    """base_dir が相対パスでも local runner が entrypoint を実行できる。

    過去バグ: 子プロセスを cwd=output/ で起動するため、相対 script パスが
    解決できず必ず失敗していた (事前 exists() は親 cwd 基準で通ってしまう)。
    """
    from core.manifest import JobManifest
    from runners.local.run import run as local_run

    jobdir = tmp_path / "j1" / "kernel"
    jobdir.mkdir(parents=True)
    (jobdir / "main.py").write_text("print('rel ok')", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    job = JobManifest.from_dict(
        {"name": "rel", "runner": "local", "identity": "local", "entrypoint": "kernel"}
    )
    assert local_run(job, Path("j1"), None) == 0
    assert (jobdir / "output" / "local_run.log").exists()


def _scored_dispatcher(tmp_path, runner_writes_score: bool, score_required: bool):
    """score 契約テスト用: runner が output/sim_result.json を書く偽 runner を組む。"""
    q = tmp_path / "queue"
    q.mkdir(exist_ok=True)
    kernel = tmp_path / "kernel"
    kernel.mkdir(exist_ok=True)
    manifest = {
        "name": "job-s",
        "runner": "local",
        "identity": "local",
        "entrypoint": "../kernel",
    }
    if score_required:
        manifest["score_required"] = True
    (q / "job-s.json").write_text(json.dumps(manifest), encoding="utf-8")

    def fake_runner(job, base, ident):
        outdir = kernel / "output"
        outdir.mkdir(exist_ok=True)
        payload = {"score": 0.75} if runner_writes_score else {"steps": 3}
        (outdir / "sim_result.json").write_text(json.dumps(payload), encoding="utf-8")
        return 0

    return Dispatcher({"local": fake_runner}, tmp_path, identities=BOOK), q


def test_scored_job_records_score_in_ledger(tmp_path):
    d, q = _scored_dispatcher(tmp_path, runner_writes_score=True, score_required=True)
    assert d.run_queue(q) == {"job-s": "finished"}
    finished = [e for e in d.ledger.read("runs.jsonl") if e["event"] == "finished"]
    assert finished[-1]["score"] == 0.75


def test_score_required_without_score_fails_closed(tmp_path):
    """score_required なのに score が無い完走は「成功ログ付きの空振り」— 完走扱いにしない。"""
    d, q = _scored_dispatcher(tmp_path, runner_writes_score=False, score_required=True)
    assert d.run_queue(q) == {"job-s": "failed"}
    events = d.ledger.read("runs.jsonl")
    assert any("score" in e["detail"] for e in events if e["event"] == "failed")


def test_score_optional_job_finishes_without_score(tmp_path):
    d, q = _scored_dispatcher(tmp_path, runner_writes_score=False, score_required=False)
    assert d.run_queue(q) == {"job-s": "finished"}
