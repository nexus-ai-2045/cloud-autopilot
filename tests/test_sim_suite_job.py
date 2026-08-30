"""jobs/sim-suite/main.py の評価契約 (score 書込) のテスト。

製品 repo の checkout を要求する実走部分は偽 runner に差し替え、
「決定論確認まで通ったら sim_result.json に有限数値 score を書く」契約だけを固定する
(score_required ジョブが score を返さないと dispatcher が完走扱いにしないため、
この書込が落ちると sim-suite は常に失敗する)。
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("sim_suite_main", ROOT / "jobs" / "sim-suite" / "main.py")
sim_suite = importlib.util.module_from_spec(_spec)
# dataclass デコレータが sys.modules 経由でモジュール名前空間を引くため、exec 前に登録する
sys.modules["sim_suite_main"] = sim_suite
_spec.loader.exec_module(sim_suite)


def test_main_writes_sim_result_with_score(tmp_path, monkeypatch):
    """全製品が決定論確認を通ると、cwd (= output/ 規約) に score 付き sim_result.json を書く。"""
    repos = tmp_path / "repos"
    (repos / "fake-product").mkdir(parents=True)
    outdir = tmp_path / "output"
    outdir.mkdir()

    fake = sim_suite.Product("fake-product", "scenario", 1, {})

    def fake_runner(repo, workdir, attempt):
        return b"same-bytes", ["fake-cmd"]  # 2 回とも同一 = 決定論 OK

    monkeypatch.setattr(sim_suite, "REPOS_ROOT", repos)
    monkeypatch.setattr(sim_suite, "STUDIO_ROOT", tmp_path / "no-studio")  # 検証は skip 経路
    monkeypatch.setattr(sim_suite, "PRODUCTS", [(fake, fake_runner)])
    monkeypatch.chdir(outdir)

    assert sim_suite.main() == 0
    result = json.loads((outdir / "sim_result.json").read_text(encoding="utf-8"))
    assert result["score"] == 1.0  # 決定論確認済み bundle 数
    assert "fake-product" in result["products"]
    assert (outdir / "studio-runs" / "fake-product.json").exists()


def test_main_fails_closed_on_nondeterminism_without_score(tmp_path, monkeypatch):
    """2 回の実行結果が一致しなければ raise し、sim_result.json (score) を書かない。"""
    repos = tmp_path / "repos"
    (repos / "fake-product").mkdir(parents=True)
    outdir = tmp_path / "output"
    outdir.mkdir()

    fake = sim_suite.Product("fake-product", "scenario", 1, {})
    counter = {"n": 0}

    def flaky_runner(repo, workdir, attempt):
        counter["n"] += 1
        return f"bytes-{counter['n']}".encode(), ["fake-cmd"]

    monkeypatch.setattr(sim_suite, "REPOS_ROOT", repos)
    monkeypatch.setattr(sim_suite, "STUDIO_ROOT", tmp_path / "no-studio")
    monkeypatch.setattr(sim_suite, "PRODUCTS", [(fake, flaky_runner)])
    monkeypatch.chdir(outdir)

    try:
        sim_suite.main()
        raised = False
    except RuntimeError as e:
        raised = True
        assert "一致しない" in str(e)
    assert raised
    assert not (outdir / "sim_result.json").exists()  # 空振りに score を残さない
