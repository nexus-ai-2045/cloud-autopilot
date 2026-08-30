"""ジョブキューと自動再開。

jobs/queue/ に置かれた manifest を順に実行する。
- 実行前に名義エイリアスを config.local.json で解決する。解決できないジョブは走らせない
- 実行状態は data/queue_state.json に永続化し、再起動しても続きから走る (自動再開)
- rejected は終端ではない: 設定を直せば次回の実行で自動的に再検証される
- runner が一時障害で落ちたら、manifest の fallback runner (local のみ) に回す
- すべての遷移は Ledger に記録する (黙って止まらない)
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from .config import ConfigError, Identity, IdentityBook
from .evaluator import ScoreError, invalidate_previous_result, read_score
from .ledger import Ledger
from .manifest import JobManifest, ManifestError

STATE_FILE = "queue_state.json"

# ジョブの終端状態。ここに入ったジョブは再実行しない (再実行は state を消して明示的に)。
# rejected は入れない: 設定不備 (未登録名義・プレースホルダ等) は config.local.json を
# 直せば解消する回復可能な状態で、終端化すると「直したのに走らない」行き止まりになる
TERMINAL = {"finished", "failed"}

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
        """queue_dir の *.json をファイル名順に処理し、{ファイル名 stem: 終了状態} を返す。

        state は manifest の name をキーに持つため、別ファイルが同じ name を宣言すると
        先に走ったジョブの終端状態を借りて黙ってスキップされてしまう。それを防ぐため、
        同一 name の 2 件目以降はここで rejected にする (state には触らない —
        正当な 1 件目の記録を重複側が上書きしないため)。
        """
        results: dict[str, str] = {}
        claimed: dict[str, Path] = {}  # name -> 最初にその name を宣言したファイル
        for path in sorted(Path(queue_dir).glob("*.json")):
            try:
                name = JobManifest.load(path).name
            except ManifestError:
                results[path.stem] = self.run_one(path)  # 拒否の記録は run_one に一元化
                continue
            first = claimed.get(name)
            if first is not None:
                msg = f"ジョブ名 '{name}' が {first.name} と重複。名前を変えるかファイルを統合する"
                print(f"[rejected] {path.stem}: {msg}", file=sys.stderr)
                self.ledger.record_run(name, "-", "-", "rejected", msg)
                results[path.stem] = "rejected"
                continue
            claimed[name] = path
            results[path.stem] = self.run_one(path)
        return results

    def run_one(self, manifest_path: Path) -> str:
        try:
            job = JobManifest.load(manifest_path)
        except ManifestError as e:
            print(f"[rejected] {manifest_path.stem}: {e}", file=sys.stderr)
            self.ledger.record_run(manifest_path.stem, "-", "-", "rejected", str(e))
            # name が読めないので stem で記録する (status 表示用)。ただし終端 state は
            # 上書きしない: stem == name の規約下で finished 済みジョブの manifest を
            # 一時的に壊すと、rejected 上書き→修復後に「state 削除なしの黙った再実行」が
            # 起きてしまう (終端のやり直しは state 削除で明示的に、の不変条件を守る)
            if self.state.get(manifest_path.stem) not in TERMINAL:
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
                # 再実行で残った前回成果物を、今回の exit 0 に紐づけない
                invalidate_previous_result(manifest_path.parent, job.entrypoint)
                code = fn(job, manifest_path.parent, run_ident)
            except Exception as e:  # runner 内の想定外は fallback に回す (握り潰さず記録)
                self.ledger.record_run(
                    job.name, runner_name, job.identity, "failed", repr(e)[:200], account=run_ident.account
                )
                continue
            if code == 0:
                # 評価契約: score を読み、score_required なのに無い/壊れた完走は
                # 「成功ログ付きの空振り」として完走扱いにしない (次の runner へ)
                try:
                    score = read_score(manifest_path.parent, job.entrypoint)
                    score_problem = "score 無し" if (job.score_required and score is None) else ""
                except ScoreError as e:
                    score, score_problem = None, str(e)
                if job.score_required and score_problem:
                    self.ledger.record_run(
                        job.name, runner_name, job.identity, "failed",
                        f"score 契約違反: {score_problem}", account=run_ident.account,
                    )
                    continue
                self.state.set(job.name, "finished", runner_name)
                self.ledger.record_run(
                    job.name, runner_name, job.identity, "finished",
                    account=run_ident.account, score=score,
                )
                return "finished"
            self.ledger.record_run(
                job.name, runner_name, job.identity, "failed", f"exit={code}", account=run_ident.account
            )
        self.state.set(job.name, "failed", "all runners exhausted")
        return "failed"
