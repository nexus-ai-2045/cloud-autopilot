"""Kaggle runner — kaggle CLI でカーネルを push し、完走を確認して出力を回収する。

前提: kaggle CLI (`pip install kaggle`) と `~/.kaggle/kaggle.json` (API トークン)。
kernel-metadata.json は repo に置かず、push 直前に config.local.json の名義から生成する
(アカウント名を repo に混入させないため)。

使い方:
    python runners/kaggle/run.py jobs/<job>/job.json
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from core.api_client import TransientError, call_with_backoff  # noqa: E402
from core.config import CONFIG_LOCAL, Identity, IdentityBook  # noqa: E402
from core.ledger import Ledger  # noqa: E402
from core.manifest import JobManifest  # noqa: E402

POLL_INTERVAL = 30
POLL_TIMEOUT = 20 * 60


def build_kernel_metadata(job: JobManifest, account: str) -> dict:
    """kernel-metadata.json の中身。アカウント名は実行時に名義帳から注入する。"""
    return {
        "id": f"{account}/{job.name}",
        "title": job.name,
        "code_file": "main.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": bool(job.gpu),
        "enable_tpu": False,
        "enable_internet": False,
        "dataset_sources": [],
        "competition_sources": [],
        "kernel_sources": [],
    }


def _kaggle_cli() -> str:
    exe = shutil.which("kaggle")
    if exe:
        return exe
    scripts = Path.home() / "AppData/Roaming/Python"
    for cand in sorted(scripts.glob("Python*/Scripts/kaggle.exe")) if scripts.exists() else []:
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


def run_job(job: JobManifest, base_dir: Path, ident: Identity) -> int:
    """dispatcher の RunnerFn 契約そのまま: (manifest, manifest の親 dir, 解決済み名義)。

    manifest の再ロードはしない (dispatcher が検証済みの job と食い違う事故を防ぐ)。
    """
    if job.runner != "kaggle":
        raise SystemExit(f"この runner は kaggle 専用 (manifest: {job.runner})")
    ledger = Ledger()
    kernel_dir = Path(base_dir).resolve() / job.entrypoint

    # kernel-metadata.json を名義帳から生成 (gitignore 済み。repo にアカウント名を置かない)
    metadata = build_kernel_metadata(job, ident.account)
    (kernel_dir / "kernel-metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    ledger.record_run(job.name, "kaggle", job.identity, "started", f"push {kernel_dir}", account=ident.account)
    out = call_with_backoff(lambda: _run(["kernels", "push", "-p", str(kernel_dir)]), api_name="kaggle:push", ledger=ledger)
    print(out.strip())
    m = re.search(r"(?:kernels|code)/([\w-]+/[\w-]+)", out)
    slug = m.group(1) if m else metadata["id"]

    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        status = call_with_backoff(lambda: _run(["kernels", "status", slug]), api_name="kaggle:status", ledger=ledger)
        print(status.strip())
        if "complete" in status.lower():
            outdir = kernel_dir / "output"
            outdir.mkdir(exist_ok=True)
            # -o (--force): ローカルに古い同名ファイルがあっても必ずクラウド側の出力で上書きする
            # (fallback 実行が先に同じ output/ に書いた場合、スキップされると証跡が混ざる)
            print(call_with_backoff(lambda: _run(["kernels", "output", slug, "-p", str(outdir), "-o"]), api_name="kaggle:output", ledger=ledger))
            # 終端の finished は dispatcher が score 検証後に書く。ここで finished を
            # 書くと、score 契約違反でも台帳に完走記録が残る。
            ledger.record_run(
                job.name, "kaggle", job.identity, "checkpoint",
                f"output collected {slug}", account=ident.account,
            )
            return 0
        if "error" in status.lower() or "cancel" in status.lower():
            ledger.record_run(job.name, "kaggle", job.identity, "failed", status.strip()[:200], account=ident.account)
            return 1
        time.sleep(POLL_INTERVAL)
    ledger.record_run(job.name, "kaggle", job.identity, "failed", "poll timeout", account=ident.account)
    return 2


if __name__ == "__main__":
    _path = Path(sys.argv[1]).resolve()
    _job = JobManifest.load(_path)
    _ident = IdentityBook.load(ROOT / CONFIG_LOCAL).resolve(_job.identity, _job.runner)
    raise SystemExit(run_job(_job, _path.parent, _ident))
