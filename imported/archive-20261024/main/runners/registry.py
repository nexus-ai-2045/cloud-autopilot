"""runner 名 → 実装の対応表。dispatcher はここ経由で runner を引く。"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runners.local.run import run as local_run  # noqa: E402


def kaggle_run(job, base_dir: Path) -> int:
    from runners.kaggle.run import run_job

    return run_job(str(Path(base_dir) / "job.json"))


def colab_run(job, base_dir: Path) -> int:
    """Colab 公式 CLI (google-colab-cli) 経由。

    制約 (一次情報 2026-08-25 確認):
    - CLI は Windows 非対応 → この環境では WSL (Alpine 実測あり) 経由で叩く
    - セットアップ未了なら明確なエラーで止まる (黙って成功したフリをしない)
    """
    script = Path(base_dir) / job.entrypoint
    if script.is_dir():
        script = script / "main.py"
    wsl = shutil.which("wsl")
    if not wsl:
        print("[colab] WSL が無い。colab-cli は Windows 非対応のため実行不可", file=sys.stderr)
        return 1
    probe = subprocess.run([wsl, "colab", "version"], capture_output=True, text=True)
    if probe.returncode != 0:
        print(
            "[colab] WSL 内に colab CLI 未セットアップ。"
            "手順: WSL 内で `uv tool install google-colab-cli` → `colab auth` (人間のブラウザ承認が必要)",
            file=sys.stderr,
        )
        return 1
    wsl_path = subprocess.run([wsl, "wslpath", str(script)], capture_output=True, text=True).stdout.strip()
    proc = subprocess.run([wsl, "colab", "exec", wsl_path], capture_output=True, text=True)
    print((proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode


RUNNERS = {
    "local": local_run,
    "kaggle": kaggle_run,
    "colab": colab_run,
    # gcloud は Phase 3 (司令塔常駐) で実装
}
