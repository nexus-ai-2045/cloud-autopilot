"""ジョブキューと自動再開。

jobs/queue/ に置かれた manifest を順に実行する。
- 実行前に名義エイリアスを config.local.json で解決する。解決できないジョブは走らせない
- 実行状態は data/queue_state.json に永続化し、再起動しても続きから走る (自動再開)
- runner が一時障害で落ちたら、manifest の fallback runner (local のみ) に回す
- すべての遷移は Ledger に記録する (黙って止まらない)
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from .config import ConfigError, Identity, IdentityBook
from .ledger import Ledger
from .manifest import JobManifest, ManifestError

STATE_FILE = "queue_state.json"

# ジョブの終端状態。ここに入ったジョブは再実行しない (再実行は state を消して明示的に)
TERMINAL = {"finished", "failed", "rejected"}

# fallback で local に回るときの名義。外部アカウントを持たない固定値
LOCAL_IDENTITY = Identity(alias="local", runner="local", account="local")


class QueueState:
    """data/queue_state.json に永続化するジョブ状態。fail-closed: 記録できなければ進めない。"""

    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / STATE_FILE
        self.state: dict[str, dict] = {}
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))

    def get(self, job_name: str) -> str:
        return self.state.get(job_name, {}).get("status", "pending")

    def set(self, job_name: str, status: str, detail: str = "") -> None:
        self.state[job_name] = {"status": status, "detail": detail}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")


# runner 契約: (manifest, manifest の親 dir, 解決済み名義) -> exit code
RunnerFn = Callable[[JobManifest, Path, Identity], int]


class Dispatcher:
    def __init__(
        self,
        runners: dict[str, RunnerFn],
        data_dir: Path,
        ledger: Ledger | None = None,
        identities: IdentityBook | None = None,
    ) -> None:
        if identities is None:
            raise ConfigError("IdentityBook が無い。名義を解決できないジョブは走らせない (fail-closed)")
        self.runners = runners
        self.state = QueueState(data_dir)
        self.ledger = ledger or Ledger(data_dir)
        self.identities = identities

    def run_queue(self, queue_dir: Path) -> dict[str, str]:
        """queue_dir の *.json を名前順に処理し、{job名: 終了状態} を返す。"""
        results: dict[str, str] = {}
        for path in sorted(Path(queue_dir).glob("*.json")):
            results[path.stem] = self._run_one(path)
        return results

    def _run_one(self, manifest_path: Path) -> str:
        try:
            job = JobManifest.load(manifest_path)
        except ManifestError as e:
            print(f"[rejected] {manifest_path.stem}: {e}", file=sys.stderr)
            self.ledger.record_run(manifest_path.stem, "-", "-", "rejected", str(e))
            self.state.set(manifest_path.stem, "rejected", str(e))
            return "rejected"

        # 終端チェックは名義解決より先 (後からの設定エラーで finished を上書きしない)
        if self.state.get(job.name) in TERMINAL:
            return self.state.get(job.name)  # 自動再開: 終端済みはスキップ

        try:
            ident = self.identities.resolve(job.identity, job.runner)
        except ConfigError as e:
            print(f"[rejected] {job.name}: {e}", file=sys.stderr)
            self.ledger.record_run(job.name, "-", job.identity, "rejected", str(e))
            self.state.set(job.name, "rejected", str(e))
            return "rejected"

        chain = [(job.runner, ident)] + [(r, LOCAL_IDENTITY) for r in job.fallback]
        for runner_name, run_ident in chain:
            fn = self.runners.get(runner_name)
            if fn is None:
                self.ledger.record_run(
                    job.name, runner_name, job.identity, "failed", "runner 未実装", account=run_ident.account
                )
                continue
            self.state.set(job.name, "running", runner_name)
            self.ledger.record_run(job.name, runner_name, job.identity, "started", account=run_ident.account)
            try:
                code = fn(job, manifest_path.parent, run_ident)
            except Exception as e:  # runner 内の想定外は fallback に回す (握り潰さず記録)
                self.ledger.record_run(
                    job.name, runner_name, job.identity, "failed", repr(e)[:200], account=run_ident.account
                )
                continue
            if code == 0:
                self.state.set(job.name, "finished", runner_name)
                self.ledger.record_run(
                    job.name, runner_name, job.identity, "finished", account=run_ident.account
                )
                return "finished"
            self.ledger.record_run(
                job.name, runner_name, job.identity, "failed", f"exit={code}", account=run_ident.account
            )
        self.state.set(job.name, "failed", "all runners exhausted")
        return "failed"
