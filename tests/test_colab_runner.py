"""runners/registry.py の colab_run のテスト。

設計方針 (runners/colab/README.md 参照):
- colab CLI は macOS / Linux ネイティブ対応。まずホストの `colab` を探す
- 無い時だけ WSL に落ちる (Windows のみ CLI 非対応のため)
- どちらも無ければ、セットアップ手順を言って止まる (fail-closed)
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.manifest import JobManifest
from runners import registry

JOB = JobManifest.from_dict(
    {"name": "colab-job", "runner": "colab", "identity": "colab-main", "entrypoint": "kernel"}
)


def _fake_which(mapping):
    return lambda name: mapping.get(name)


def test_native_colab_cli_is_preferred_even_when_wsl_exists(tmp_path, monkeypatch):
    """colab と WSL の両方がある環境でも、ネイティブ colab を優先し WSL を経由しない。"""
    (tmp_path / "kernel").mkdir()
    (tmp_path / "kernel" / "main.py").write_text("", encoding="utf-8")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(
        registry.shutil, "which", _fake_which({"colab": "/usr/bin/colab", "wsl": "/usr/bin/wsl"})
    )
    monkeypatch.setattr(registry.subprocess, "run", fake_run)
    assert registry.colab_run(JOB, tmp_path, None) == 0
    assert calls == [["/usr/bin/colab", "exec", str(tmp_path / "kernel" / "main.py")]]


def test_no_colab_and_no_wsl_fails_closed_with_setup_hint(tmp_path, monkeypatch, capsys):
    """colab も WSL も無い環境では、セットアップ手順を言って exit 1 (黙って成功しない)。

    過去バグ: WSL の有無だけを見ていたため、macOS / Linux では colab CLI を
    インストール済みでも「WSL が無い」という誤った理由で必ず失敗した。
    """
    monkeypatch.setattr(registry.shutil, "which", _fake_which({}))
    assert registry.colab_run(JOB, tmp_path, None) == 1
    err = capsys.readouterr().err
    assert "google-colab-cli" in err  # 復旧手順を必ず示す
    assert "WSL が無い" not in err
