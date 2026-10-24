"""Kaggle runner — kaggle CLI でカーネルを push し、完走を確認して出力を回収する。

前提: `~/.kaggle/kaggle.json` (接続実測 2026-08-25 済み)。
使い方:
    python runners/kaggle/run.py jobs/kaggle-gpu-smoke.json
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.api_client import TransientError, call_with_backoff  # noqa: E402
from core.ledger import Ledger  # noqa: E402
from core.manifest import JobManifest  # noqa: E402

POLL_INTERVAL = 30
POLL_TIMEOUT = 20 * 60


def _kaggle_cli() -> str:
    exe = shutil.which("kaggle")
    if exe:
        return exe
    for cand in (
        Path.home() / "AppData/Roaming/Python/Python313/Scripts/kaggle.exe",
        Path.home() / "AppData/Local/Programs/Python/Python313/Scripts/kaggle.exe",
    ):
        if cand.exists():
            return str(cand)
    raise RuntimeError("kaggle CLI が見つからない (pip install kaggle)")


def _run(args: list[str]) -> str:
    proc = subprocess.run([_kaggle_cli(), *args], capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        m = re.search(r"\b(429|500|502|503|504)\b", out)
        if m:
            raise TransientError(int(m.group(1)), out.strip()[:300])
        raise RuntimeError(f"kaggle CLI 失敗 (exit={proc.returncode}): {out.strip()[:500]}")
    return out


def run_job(manifest_path: str) -> int:
    job = JobManifest.load(manifest_path)
    if job.runner != "kaggle":
        raise SystemExit(f"この runner は kaggle 専用 (manifest: {job.runner})")
    ledger = Ledger()
    kernel_dir = Path(manifest_path).resolve().parent / job.entrypoint
    ledger.record_run(job.name, "kaggle", job.identity, "started", f"push {kernel_dir}")

    out = call_with_backoff(lambda: _run(["kernels", "push", "-p", str(kernel_dir)]), api_name="kaggle:push", ledger=ledger)
    print(out.strip())
    m = re.search(r"(?:kernels|code)/([\w-]+/[\w-]+)", out)
    slug = m.group(1) if m else f"{job.identity}/{job.name}"

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = call_with_backoff(lambda: _run(["kernels", "status", slug]), api_name="kaggle:status", ledger=ledger)
        print(status.strip())
        if "complete" in status.lower():
            outdir = kernel_dir / "output"
            outdir.mkdir(exist_ok=True)
            print(call_with_backoff(lambda: _run(["kernels", "output", slug, "-p", str(outdir)]), api_name="kaggle:output", ledger=ledger))
            ledger.record_run(job.name, "kaggle", job.identity, "finished", slug)
            return 0
        if "error" in status.lower() or "cancel" in status.lower():
            ledger.record_run(job.name, "kaggle", job.identity, "failed", status.strip()[:200])
            return 1
        time.sleep(POLL_INTERVAL)
    ledger.record_run(job.name, "kaggle", job.identity, "failed", "poll timeout")
    return 2


if __name__ == "__main__":
    raise SystemExit(run_job(sys.argv[1]))
