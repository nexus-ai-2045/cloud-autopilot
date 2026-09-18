"""kaggle runner の kernel-metadata 生成と dispatcher 契約 (CLI 実行なしで検証できる部分)。"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import Identity
from core.ledger import Ledger
from core.manifest import JobManifest
from runners.kaggle.run import build_kernel_metadata


def _job(**over) -> JobManifest:
    base = {"name": "sim-x", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "kernel"}
    return JobManifest.from_dict({**base, **over})


def test_metadata_id_comes_from_resolved_account():
    """アカウント名は repo に無い。実行時に名義帳から注入される。"""
    meta = build_kernel_metadata(_job(), "someone")
    assert meta["id"] == "someone/sim-x"
    assert meta["title"] == "sim-x"


def test_metadata_gpu_follows_manifest():
    assert build_kernel_metadata(_job(gpu=True), "a")["enable_gpu"] is True
    assert build_kernel_metadata(_job(), "a")["enable_gpu"] is False


def test_metadata_private_and_offline_by_default():
    """公開 repo でもジョブ実体は private kernel / internet 無効が既定。"""
    meta = build_kernel_metadata(_job(), "a")
    assert meta["is_private"] is True
    assert meta["enable_internet"] is False


def test_kaggle_adapter_honors_dispatcher_contract(tmp_path, monkeypatch):
    """registry の kaggle adapter は dispatcher が渡した job/base_dir をそのまま使う。

    manifest ファイル名が job.json 以外 (jobs/queue/*.json 等) でも動くこと。
    過去バグ: manifest 名を job.json に決め打ちして再ロードし、queue 経由の
    kaggle ジョブが必ず FileNotFoundError → 黙って fallback に落ちていた。
    """
    import runners.kaggle.run as kr
    from runners.registry import kaggle_run

    kernel_dir = tmp_path / "kernels" / "k1"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "main.py").write_text("print('x')", encoding="utf-8")
    queue_dir = tmp_path / "queue"
    queue_dir.mkdir()

    job = JobManifest.from_dict(
        {"name": "my-kaggle-job", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "../kernels/k1"}
    )
    calls = []

    def fake_cli(args):
        calls.append(args)
        if args[:2] == ["kernels", "push"]:
            return "Kernel version 1 successfully pushed. kernels/test-kaggle-user/my-kaggle-job"
        if args[:2] == ["kernels", "status"]:
            return 'has status "KernelWorkerStatus.COMPLETE"'
        return "downloaded"

    monkeypatch.setattr(kr, "_run", fake_cli)
    monkeypatch.setattr(kr, "Ledger", lambda: Ledger(tmp_path))

    rc = kaggle_run(job, queue_dir, Identity("kaggle-main", "kaggle", "test-kaggle-user"))
    assert rc == 0

    push = next(c for c in calls if c[:2] == ["kernels", "push"])
    assert Path(push[3]).resolve() == kernel_dir.resolve()  # queue/job.json を探しに行かない
    meta = json.loads((kernel_dir / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert meta["id"] == "test-kaggle-user/my-kaggle-job"

    output = next(c for c in calls if c[:2] == ["kernels", "output"])
    assert "-o" in output  # 古いローカルコピーでスキップさせない (--force)

    events = Ledger(tmp_path).read("runs.jsonl")
    assert any(e["event"] == "checkpoint" for e in events)
    assert not any(e["event"] == "finished" for e in events)


@pytest.mark.parametrize(
    "text, expected",
    [
        ('some-error-lab/my-cancel-job has status "KernelWorkerStatus.RUNNING"', "RUNNING"),
        ('x/y has status "KernelWorkerStatus.COMPLETE"', "COMPLETE"),
        ('x/y has status "KernelWorkerStatus.ERROR"', "ERROR"),
        ('x/y has status "KernelWorkerStatus.CANCEL_REQUESTED"', "CANCEL_REQUESTED"),
        ("garbage without token", None),
    ],
)
def test_parse_kernel_status_ignores_words_inside_slug(text, expected):
    """過去バグ: 行全体への部分一致で、slug に error/cancel/complete を含むと誤判定していた。"""
    from runners.kaggle.run import parse_kernel_status

    assert parse_kernel_status(text) == expected


def test_kaggle_adapter_does_not_duplicate_started_event(tmp_path, monkeypatch):
    """started は dispatcher が記録する。runner 側は checkpoint のみ (二重記録防止)。"""
    import runners.kaggle.run as kr
    from runners.registry import kaggle_run

    kernel_dir = tmp_path / "kernels" / "k1"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "main.py").write_text("print('x')", encoding="utf-8")
    (tmp_path / "queue").mkdir()
    job = JobManifest.from_dict(
        {"name": "j2", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "../kernels/k1"}
    )

    def fake_cli(args):
        if args[:2] == ["kernels", "status"]:
            return 'has status "KernelWorkerStatus.COMPLETE"'
        return "ok"

    monkeypatch.setattr(kr, "_run", fake_cli)
    ledger = Ledger(tmp_path)
    monkeypatch.setattr(kr, "Ledger", lambda: ledger)
    assert kaggle_run(job, tmp_path / "queue", Identity("kaggle-main", "kaggle", "u")) == 0
    events = [e["event"] for e in ledger.read("runs.jsonl")]
    assert "started" not in events
    assert "checkpoint" in events


def test_running_kernel_with_error_in_slug_is_not_failed(tmp_path, monkeypatch):
    """polling ループが slug 中の語で誤判定しない (純粋関数だけでなく使われ方を固定する)。

    過去バグ: RUNNING 中でも slug に "error" があると行全体の部分一致で failed 扱いになった。
    """
    import runners.kaggle.run as kr
    from runners.registry import kaggle_run

    kernel_dir = tmp_path / "kernels" / "k1"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "main.py").write_text("print('x')", encoding="utf-8")
    (tmp_path / "queue").mkdir()
    job = JobManifest.from_dict(
        {"name": "error-lab-job", "runner": "kaggle", "identity": "kaggle-main", "entrypoint": "../kernels/k1"}
    )
    statuses = iter(["RUNNING", "COMPLETE"])

    def fake_cli(args):
        if args[:2] == ["kernels", "status"]:
            return f'some-error-lab/error-lab-job has status "KernelWorkerStatus.{next(statuses)}"'
        return "ok"

    monkeypatch.setattr(kr, "_run", fake_cli)
    monkeypatch.setattr(kr, "Ledger", lambda: Ledger(tmp_path))
    monkeypatch.setattr(kr.time, "sleep", lambda _: None)
    assert kaggle_run(job, tmp_path / "queue", Identity("kaggle-main", "kaggle", "u")) == 0
