"""cloud-autopilot 入口。

使い方:
    python autopilot.py queue              # jobs/queue/*.json を順に実行 (自動再開つき)
    python autopilot.py run <manifest>     # 単発ジョブ実行
    python autopilot.py status             # 台帳とキュー状態の要約
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.dispatcher import Dispatcher  # noqa: E402
from core.ledger import Ledger  # noqa: E402
from runners.registry import RUNNERS  # noqa: E402

DATA = ROOT / "data"
QUEUE = ROOT / "jobs" / "queue"


def cmd_queue() -> int:
    QUEUE.mkdir(parents=True, exist_ok=True)
    results = Dispatcher(RUNNERS, DATA).run_queue(QUEUE)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(v in ("finished",) for v in results.values()) or not results else 1


def cmd_run(manifest: str) -> int:
    path = Path(manifest)
    result = Dispatcher(RUNNERS, DATA)._run_one(path)
    print(result)
    return 0 if result == "finished" else 1


def cmd_status() -> int:
    ledger = Ledger(DATA)
    runs = ledger.read("runs.jsonl")
    limits = ledger.read("rate_limit.jsonl")
    state_file = DATA / "queue_state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    print(json.dumps(
        {
            "実行イベント数": len(runs),
            "直近の実行": runs[-3:],
            "レート制限イベント数": len(limits),
            "キュー状態": state,
        },
        ensure_ascii=False, indent=2,
    ))
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] not in ("queue", "run", "status"):
        print(__doc__)
        raise SystemExit(2)
    if args[0] == "queue":
        raise SystemExit(cmd_queue())
    if args[0] == "run":
        raise SystemExit(cmd_run(args[1]))
    raise SystemExit(cmd_status())
