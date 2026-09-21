"""autopilot.py の CLI を入口から通す E2E (隔離コピー上で実行。repo の data/ には触らない)。"""

import json
import os
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


def _run(clone, *args, extra_env=None):
    child_env = {**os.environ, **(extra_env or {})}
    return subprocess.run(
        [sys.executable, "autopilot.py", *args], cwd=str(clone), env=child_env,
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


@pytest.mark.parametrize("args, expected", [(("status",), 0), (("run",), 2)])
def test_cli_survives_non_utf8_console(clone, args, expected):
    """日本語メッセージを非 UTF-8 コンソール (英語 Windows の cp1252 等) でも落とさず出す。

    過去バグ: CI の windows ランナー (cp1252) で print が UnicodeEncodeError になり、
    clone して最初のコマンドが exit 1 で落ちた。日本語 Windows (cp932) では再現しないため
    手元のテストでは見えなかった。コンソールの文字コードを cp1252 に強制して OS を問わず再現する。
    """
    r = _run(clone, *args, extra_env={"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"})
    assert "UnicodeEncodeError" not in r.stderr
    assert r.returncode == expected
