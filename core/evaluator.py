"""評価契約 (evaluator contract)。

ループ (ラチェット・探索) に乗るジョブは、出力 `<entrypoint>/output/sim_result.json` に
**有限の数値 `score`** を書く。これが「機械採点できる実験だけをループに入れる」ための
最小契約で、score_required のジョブが score を返さなければ完走扱いにしない (fail-closed)。
「成功ログ付きで何もしていない」空振り (脅威モデル a) をここで検知する。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

RESULT_FILE = "sim_result.json"


class ScoreError(ValueError):
    """score が読めない・不正。理由を必ずメッセージに含める。"""


def output_dir(base_dir: Path | str, entrypoint: str) -> Path:
    """runner 規約と同じ解決: entrypoint が dir ならその直下、file なら親の output/。"""
    target = Path(base_dir) / entrypoint
    d = target if target.is_dir() else target.parent
    return d / "output"


def invalidate_previous_result(base_dir: Path | str, entrypoint: str) -> None:
    """今回の invocation に前回の sim_result.json を混ぜない。

    終端 state を消して再実行すると output/ は残る。runner が exit 0 でも
    新しい score を書かない場合、古いファイルを読むと空振りを完走にできる。
    """
    path = output_dir(base_dir, entrypoint) / RESULT_FILE
    if path.is_file():
        path.unlink()


def read_score(base_dir: Path | str, entrypoint: str) -> float | None:
    """output/sim_result.json の score を返す。

    - ファイルまたは score キーが無い → None (契約を宣言していないジョブは自由)
    - JSON 破損・非 object・非数値・NaN/inf → ScoreError (壊れた採点は「無し」と区別して止める)
    """
    path = output_dir(base_dir, entrypoint) / RESULT_FILE
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ScoreError(f"{path} が JSON として読めない: {e}") from e
    if not isinstance(data, dict):
        raise ScoreError(f"{path} のトップレベルが object ではない: {type(data).__name__}")
    if "score" not in data:
        return None
    value = data["score"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ScoreError(f"score が有限の数値でない: {value!r} ({path})")
    return float(value)
