"""実行・レート制限台帳。

すべての外部 API 呼び出しと 429/5xx の発生を JSONL に追記する。
「体感はあるが実測がない」を無くすための最小記録層。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LEDGER_DIR = Path(__file__).resolve().parent.parent / "data"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Ledger:
    """JSONL 追記のみの台帳。ファイル単位で用途を分ける。

    - runs.jsonl: ジョブ実行の開始/終了
    - rate_limit.jsonl: 429 等のレート制限イベント
    """

    def __init__(self, ledger_dir: Path | str = DEFAULT_LEDGER_DIR) -> None:
        self.dir = Path(ledger_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _append(self, filename: str, record: dict) -> dict:
        record = {"at": _now_iso(), **record}
        path = self.dir / filename
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def record_run(
        self,
        job: str,
        runner: str,
        identity: str,
        event: str,
        detail: str = "",
        account: str = "",
        score: float | None = None,
    ) -> dict:
        """event: started / finished / failed / rejected / checkpoint

        identity は manifest のエイリアス、account は解決済みの実アカウント名。
        両方残すことで「どの名義で本当に走ったか」を後から突合できる
        (data/ は gitignore 済みのローカル生成物。repo には入らない)。
        """
        record = {
            "job": job,
            "runner": runner,
            "identity": identity,
            "account": account,
            "event": event,
            "detail": detail,
        }
        if score is not None:  # 評価契約 (core/evaluator.py) を宣言したジョブだけが持つ列
            record["score"] = score
        return self._append("runs.jsonl", record)

    def record_rate_limit(self, api: str, status: int, wait_seconds: float, attempt: int) -> dict:
        return self._append(
            "rate_limit.jsonl",
            {"api": api, "status": status, "wait_seconds": wait_seconds, "attempt": attempt},
        )

    def read(self, filename: str) -> list[dict]:
        path = self.dir / filename
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
