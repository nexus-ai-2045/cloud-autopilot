"""local runner — このマシンで entrypoint (Python スクリプト) を実行する。

クラウド runner の fallback 先。identity は `local` 固定。
出力は entrypoint と同階層の output/ に置く規約 (kaggle runner と同じ形)。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(job, base_dir: Path, ident=None) -> int:
    """dispatcher の RunnerFn 契約: (JobManifest, manifest の親 dir, 解決済み名義) -> exit code

    local は外部名義を持たないため ident は使わない (契約の形だけ揃える)。
    """
    # resolve 必須: 子プロセスは cwd=output/ で走るため、相対パスのままだと見つからない
    script = (Path(base_dir) / job.entrypoint).resolve()
    if script.is_dir():
        script = script / "main.py"
    if not script.exists():
        print(f"[local] entrypoint が無い: {script}", file=sys.stderr)
        return 1
    outdir = script.parent / "output"
    outdir.mkdir(exist_ok=True)
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(outdir),  # 成果物は output/ に落ちる
        capture_output=True,
        text=True,
        timeout=30 * 60,
    )
    (outdir / "local_run.log").write_text(
        (proc.stdout or "") + (proc.stderr or ""), encoding="utf-8"
    )
    print((proc.stdout or "").strip())
    return proc.returncode
