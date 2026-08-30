"""core/evaluator.py (評価契約 L2) のテスト。

契約: ループに乗るジョブは output/sim_result.json に有限の数値 score を書く。
score_required のジョブが score を返さなければ完走扱いにしない (fail-closed)。
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.evaluator import RESULT_FILE, ScoreError, output_dir, read_score


def _write_result(outdir: Path, payload: dict) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / RESULT_FILE).write_text(json.dumps(payload), encoding="utf-8")


def test_output_dir_for_dir_entrypoint(tmp_path):
    (tmp_path / "kernel").mkdir()
    assert output_dir(tmp_path, "kernel") == tmp_path / "kernel" / "output"


def test_output_dir_for_file_entrypoint(tmp_path):
    (tmp_path / "run.py").write_text("", encoding="utf-8")
    assert output_dir(tmp_path, "run.py") == tmp_path / "output"


def test_read_score_roundtrip(tmp_path):
    (tmp_path / "kernel").mkdir()
    _write_result(tmp_path / "kernel" / "output", {"score": 0.81, "steps": 21})
    assert read_score(tmp_path, "kernel") == 0.81


def test_read_score_missing_file_is_none(tmp_path):
    (tmp_path / "kernel").mkdir()
    assert read_score(tmp_path, "kernel") is None


def test_read_score_missing_key_is_none(tmp_path):
    (tmp_path / "kernel").mkdir()
    _write_result(tmp_path / "kernel" / "output", {"steps": 21})
    assert read_score(tmp_path, "kernel") is None


@pytest.mark.parametrize("bad", ["0.8", None, True, float("nan"), float("inf")])
def test_read_score_rejects_non_finite_or_non_numeric(tmp_path, bad):
    (tmp_path / "kernel").mkdir()
    _write_result(tmp_path / "kernel" / "output", {"score": bad})
    with pytest.raises(ScoreError):
        read_score(tmp_path, "kernel")


def test_read_score_broken_json_raises(tmp_path):
    outdir = tmp_path / "kernel" / "output"
    outdir.mkdir(parents=True)
    (outdir / RESULT_FILE).write_text("{broken", encoding="utf-8")
    with pytest.raises(ScoreError):
        read_score(tmp_path, "kernel")


@pytest.mark.parametrize("raw", ["null", "1", "[1]", "\"x\""])
def test_read_score_rejects_non_object_container(tmp_path, raw):
    """トップレベルが object 以外なら TypeError ではなく ScoreError。

    dispatcher は ScoreError だけを契約違反として掴む。TypeError だと
    キュー全体が止まる。
    """
    outdir = tmp_path / "kernel" / "output"
    outdir.mkdir(parents=True)
    (outdir / RESULT_FILE).write_text(raw, encoding="utf-8")
    with pytest.raises(ScoreError):
        read_score(tmp_path, "kernel")
