"""runner 名 → 実装の対応表。dispatcher はここ経由で runner を引く。

runner 契約 (core/dispatcher.py の RunnerFn):
    (JobManifest, manifest の親 dir, 解決済み Identity) -> exit code
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runners.local.run import run as local_run  # noqa: E402


def kaggle_run(job, base_dir: Path, ident) -> int:
    from runners.kaggle.run import run_job

    return run_job(job, base_dir, ident)


def colab_run(job, base_dir: Path, ident) -> int:
    """Colab 公式 CLI (google-colab-cli) 経由。

    制約 (一次情報 2026-08-25 確認):
    - CLI は Windows 非対応 → Windows では WSL 経由で叩く
    - セットアップ未了なら明確なエラーで止まる (黙って成功したフリをしない)
    - 実行に使う Google アカウントは `colab auth` した名義。manifest の identity と
      一致しているかは人間がセットアップ時に確認する (CLI からは読めない)
    """
    script = Path(base_dir) / job.entrypoint
    if script.is_dir():
        script = script / "main.py"
    wsl = shutil.which("wsl")
    if not wsl:
        print("[colab] WSL が無い。colab-cli は Windows 非対応のため実行不可", file=sys.stderr)
        return 1
    # encoding 明示: WSL の UTF-8 出力を Windows のロケール (cp932 等) で decode すると化ける
    wsl_run = lambda args: subprocess.run(  # noqa: E731
        [wsl, *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    probe = wsl_run(["colab", "version"])
    if probe.returncode != 0:
        print(
            "[colab] WSL 内に colab CLI 未セットアップ。"
            "手順: WSL 内で `uv tool install google-colab-cli` → `colab auth` (ブラウザ承認が必要)",
            file=sys.stderr,
        )
        return 1
    conv = wsl_run(["wslpath", str(script)])
    wsl_path = conv.stdout.strip()
    if conv.returncode != 0 or not wsl_path:
        print(f"[colab] wslpath 変換に失敗: {script} ({conv.stderr.strip()})", file=sys.stderr)
        return 1
    proc = wsl_run(["colab", "exec", wsl_path])
    print((proc.stdout or "") + (proc.stderr or ""))
    return proc.returncode


RUNNERS = {
    "local": local_run,
    "kaggle": kaggle_run,
    "colab": colab_run,
}
