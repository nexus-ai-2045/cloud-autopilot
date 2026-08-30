"""ジョブ manifest の読み込みと構造検証。

manifest は「どのシミュレーターを・どの実行環境で・どの名義で回すか」の宣言。
identity フィールドは必須で、値は config.local.json のエイリアス名 (実アカウント名は
repo に置かない)。エイリアスの解決と検証は core/config.py の IdentityBook が行う。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# この repo の実行環境は 3 つだけ (責務: シミュレーターを無料枠クラウドで回す)
VALID_RUNNERS = {"colab", "kaggle", "local"}


class ManifestError(ValueError):
    """manifest の検証エラー。理由を必ずメッセージに含める。"""


@dataclass(frozen=True)
class JobManifest:
    name: str
    runner: str
    identity: str  # config.local.json のエイリアス名
    entrypoint: str
    gpu: bool = False
    notes: str = ""
    # fallback は名義の取り違えを避けるため local のみ許可 (外部名義を持たない)
    fallback: tuple = ()
    # 評価契約: true なら output/sim_result.json に有限数値 score が必須 (core/evaluator.py)
    score_required: bool = False

    @classmethod
    def from_dict(cls, raw: dict) -> "JobManifest":
        missing = [k for k in ("name", "runner", "identity", "entrypoint") if not raw.get(k)]
        if missing:
            raise ManifestError(f"必須フィールドが無い: {missing}")
        runner = raw["runner"]
        if runner not in VALID_RUNNERS:
            raise ManifestError(f"未知の runner: {runner} (有効: {sorted(VALID_RUNNERS)})")
        fallback = tuple(raw.get("fallback", []))
        bad = [r for r in fallback if r != "local"]
        if bad:
            raise ManifestError(f"fallback に指定できるのは local のみ (指定: {bad})。外部名義の自動振替は事故のもと")
        return cls(
            name=raw["name"],
            runner=runner,
            identity=raw["identity"],
            entrypoint=raw["entrypoint"],
            gpu=bool(raw.get("gpu", False)),
            notes=raw.get("notes", ""),
            fallback=fallback,
            score_required=bool(raw.get("score_required", False)),
        )

    @classmethod
    def load(cls, path: Path | str) -> "JobManifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
