"""バックオフ付き実行ヘルパー。

外部 API / CLI を裸で叩かず、必ずここを通す。
retry は 429/500/502/503/504 のみ。初期 5 秒・最大 60 秒・倍率 2・最大 3 回。
「原因が消えていないのに繰り返さない」を原則に、それ以外のエラーは再試行しない。
発生したレート制限はすべて Ledger に記録する。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .ledger import Ledger

RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_INITIAL = 5.0
BACKOFF_MAX = 60.0
BACKOFF_FACTOR = 2.0
MAX_RETRIES = 3


class TransientError(Exception):
    """一時障害。status を持ち、retryable かどうかの判定に使う。"""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(message or f"status={status}")
        self.status = status


def backoff_schedule(max_retries: int = MAX_RETRIES) -> list[float]:
    """待ち秒数の列。テストで固定的に検証できるよう純粋関数にする。"""
    waits = []
    wait = BACKOFF_INITIAL
    for _ in range(max_retries):
        waits.append(min(wait, BACKOFF_MAX))
        wait *= BACKOFF_FACTOR
    return waits


def call_with_backoff(
    fn: Callable[[], object],
    *,
    api_name: str,
    ledger: Ledger | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> object:
    """fn を実行し、TransientError(retryable) のみ再試行する。

    未知の例外は再試行しない (「とりあえず再試行」をしない)。
    """
    ledger = ledger or Ledger()
    waits = backoff_schedule()
    for attempt, wait in enumerate([0.0, *waits]):
        if wait:
            sleep(wait)
        try:
            return fn()
        except TransientError as e:
            if e.status not in RETRYABLE_STATUSES:
                raise
            ledger.record_rate_limit(api=api_name, status=e.status, wait_seconds=wait, attempt=attempt)
            last = e
    raise last
