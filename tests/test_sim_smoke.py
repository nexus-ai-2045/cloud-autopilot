"""サンプルシミュレーション (jobs/sim-smoke) の再現性。

シミュレーター側の前提「シード固定で再現できること」を、運ぶ側の repo でも
サンプルで実証しておく (README の設計方針 4)。
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "jobs" / "sim-smoke" / "kernel" / "main.py"


def _run_once(workdir: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads((workdir / "sim_result.json").read_text(encoding="utf-8"))


def test_same_seed_same_result(tmp_path):
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    a = _run_once(a_dir)
    b = _run_once(b_dir)
    # 実行時刻と GPU の有無は環境依存なので除外し、シミュレーション結果本体を比較
    for key in ("at", "gpu"):
        a.pop(key), b.pop(key)
    assert a == b
    assert a["seed"] == 42
    assert a["steps"] >= 1
    assert 0.0 <= a["segregation_index"] <= 1.0


def test_simulation_converges_meaningfully(tmp_path):
    """Schelling モデルの既知の性質: 閾値 0.3 でも分居が進む (同類率が上がる)。"""
    result = _run_once(tmp_path)
    assert result["unhappy_remaining"] == 0  # 収束している
    assert result["segregation_index"] > 0.5  # ランダム配置 (~0.5) より分居が進む
