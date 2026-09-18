"""autopilot.py の CLI を入口から通す E2E (隔離コピー上で実行。repo の data/ には触らない)。"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def clone(tmp_path):
    dst = tmp_path / "clone"
    ignore = shutil.ignore_patterns("output", "__pycache__", "kernel-metadata.json")
    dst.mkdir()
    for name in ("autopilot.py", "config.example.json"):
        shutil.copy(ROOT / name, dst / name)
    for name in ("core", "runners"):
        shutil.copytree(ROOT / name, dst / name, ignore=ignore)
    shutil.copytree(ROOT / "jobs", dst / "jobs", ignore=ignore)
    return dst


def _run(clone, *args):
    return subprocess.run(
        [sys.executable, "autopilot.py", *args], cwd=str(clone),
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )


def _write_config(clone):
    (clone / "config.local.json").write_text(
        json.dumps({"identities": {"local": {"runner": "local", "account": "local"}}}), encoding="utf-8"
    )


def test_queue_without_config_fails_closed(clone):
    r = _run(clone, "queue")
    assert r.returncode == 2
    assert "config.example.json" in r.stderr  # 復旧手順を言って止まる


def test_clean_clone_queue_succeeds_and_records_score(clone):
    """README 手順 2: clean clone + local 名義だけで同梱 queue が exit 0 になる。"""
    _write_config(clone)
    r = _run(clone, "queue")
    assert r.returncode == 0, r.stdout + r.stderr
    runs = [json.loads(x) for x in (clone / "data" / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    finished = [e for e in runs if e["event"] == "finished"]
    assert finished and isinstance(finished[-1].get("score"), float)


def test_run_without_manifest_arg_shows_usage(clone):
    assert _run(clone, "run").returncode == 2


def test_status_works_on_empty_ledger(clone):
    r = _run(clone, "status")
    assert r.returncode == 0
    json.loads(r.stdout)
