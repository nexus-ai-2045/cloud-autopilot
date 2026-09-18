"""sim-suite — メタ安全保障4シミュレーターを実走し、studio-run-bundle を生成する。

Phase 4 (横展開) の最初のスライス。各製品を **2回** 実行して出力バイト列を比較し、
一致した時だけ deterministic な run bundle を書く (不一致は fail-closed で失敗)。

- 製品コードはここへ移さない。各公開 repo の checkout を外部から参照する
  (SIM_REPOS_ROOT 環境変数、既定は ../../..//../public = .repos/<ws>/public 配置)
- bundle 契約の正本は meta-security-sim/schemas/studio-run-bundle.schema.json。
  checkout が見つかれば schema 検証まで行い、無ければ skip を明示する
- 数値・結果は各シミュレーターの実験用仮説値であり、現実の予測ではない
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

JOB_DIR = Path(__file__).resolve().parent
REPOS_ROOT = Path(os.environ.get("SIM_REPOS_ROOT") or JOB_DIR.parents[3] / "public")
STUDIO_ROOT = Path(
    os.environ.get("META_SECURITY_SIM_ROOT")
    or JOB_DIR.parents[3] / "private" / "meta-security-sim"
)
RUN_TIMEOUT_SEC = 10 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Product:
    product_id: str
    scenario_id: str
    seed: int
    parameters: dict


@dataclass(frozen=True)
class RunResult:
    """1 回の製品実行の結果。output は決定論比較の対象、stdout は実行 receipt の対象。"""

    output: bytes
    cmd: list
    stdout: bytes
    # 製品側が出す証拠 (run_id / hash 等)。run.completed の payload へそのまま束縛する
    product_evidence: dict | None = None


ADAPTER_ID = "cloud-autopilot/sim-suite"


def resolve_source_revision(repo: Path) -> str:
    """実行対象 checkout の exact HEAD を返す。dirty なら receipt が嘘になるため fail-closed。"""
    head = run_command(["git", "rev-parse", "HEAD"], cwd=repo).stdout.decode("ascii").strip()
    if len(head) != 40:
        raise RuntimeError(f"{repo.name}: git HEAD を解決できない ({head!r})")
    dirty = run_command(["git", "status", "--porcelain"], cwd=repo).stdout.strip()
    if dirty:
        raise RuntimeError(
            f"{repo.name}: checkout が dirty のため source_revision を主張できない\n"
            + dirty.decode("utf-8", "replace")[:500]
        )
    return head


def run_command(cmd: list[str], cwd: Path, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=False,
        timeout=RUN_TIMEOUT_SEC, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            + (proc.stderr or b"").decode("utf-8", "replace")[-2000:]
        )
    return proc


def resolve_npm() -> str:
    npm = os.environ.get("NPM_CMD") or shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        raise RuntimeError("npm が見つからない。NPM_CMD 環境変数で指定する")
    return npm


def run_ghost(repo: Path, workdir: Path, attempt: int) -> RunResult:
    out = workdir / f"ghost-attempt{attempt}.json"
    cmd = [
        sys.executable, "-m", "ghost_in_the_sim.batch_cli",
        "--output", str(out), "--seed", "42",
        "--actual-ai-trace", "fixtures/actual-ai-trace-seed42.json",
    ]
    proc = run_command(cmd, cwd=repo, env_extra={"PYTHONPATH": "src"})
    return RunResult(out.read_bytes(), cmd, proc.stdout)


def run_space(repo: Path, workdir: Path, attempt: int) -> RunResult:
    # run_bundle.py は既存 path への上書きを拒否する (仕様) ため、実行ごとに一意な path を使う
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"-{os.getpid()}"
    out = workdir / f"space-run-bundle-{tag}-attempt{attempt}.json"
    cmd = [sys.executable, "scripts/run_bundle.py", str(out)]
    proc = run_command(cmd, cwd=repo)
    # 製品側の再実行検証 (fixture 再読込 + runtime 再実行 + canonical 等値) を通してから採用する
    run_command([sys.executable, "scripts/run_bundle.py", "--verify", str(out)], cwd=repo)
    output = out.read_bytes()
    bundle = json.loads(output.decode("utf-8"))
    if bundle["run_request"]["seed"] != SPACE_SEED:
        raise RuntimeError("space-civilization-choice: 製品 bundle の seed が Product 定義と一致しない")
    evidence = {
        "product_run_id": bundle["run_id"],
        "product_event_count": bundle["evidence"]["event_count"],
        "product_event_stream_hash": bundle["evidence"]["event_stream_hash"],
        "product_event_stream_head_hash": bundle["evidence"]["event_stream_head_hash"],
        "product_comparison_hash": bundle["replay"]["comparison_hash"],
        "product_verify": "run_bundle.py --verify PASS",
    }
    return RunResult(output, cmd, proc.stdout, evidence)


def run_fiction(repo: Path, workdir: Path, attempt: int) -> RunResult:
    out = workdir / f"fiction-attempt{attempt}.json"
    cmd = [
        sys.executable, "-m", "fiction_forks", "social",
        "--scenario", "scenarios/japan-2036/scenario.json",
        "--intervention", "interventions/doraemon-public-tools.json",
        "--social-config", "scenarios/japan-2036/social.json",
        "--provider", "fixture",
        "--fixture", "fixtures/social/japan-2036-cooperation.jsonl",
        "--seed", "42", "--output", str(out), "--overwrite",
    ]
    proc = run_command(cmd, cwd=repo, env_extra={"PYTHONPATH": "src"})
    # fiction_forks CLI はエラーでも exit 0 の場合があるため、内容で fail-closed に判定する
    stdout_text = proc.stdout.decode("utf-8", "replace")
    if '"status": "error"' in stdout_text or not out.exists():
        raise RuntimeError(f"fiction-forks run failed: {stdout_text[-500:]}")
    return RunResult(out.read_bytes(), cmd, proc.stdout)


def run_quiet(repo: Path, workdir: Path, attempt: int) -> RunResult:
    cmd = [resolve_npm(), "run", "simulate", "--silent"]
    proc = run_command(cmd, cwd=repo / "app")
    return RunResult(proc.stdout, cmd, proc.stdout)


# space-civilization-choice の三分岐 fixture が共有する seed (fixtures/phase1_*.json)
SPACE_SEED = 20260828

PRODUCTS: list[tuple[Product, object]] = [
    (Product("ghost-in-the-sim", "distributed-crisis-response", 42,
             {"trace": "fixtures/actual-ai-trace-seed42.json"}), run_ghost),
    (Product("space-civilization-choice", "three-branch-run-bundle", SPACE_SEED,
             {"entrypoint": "scripts/run_bundle.py", "verified_by": "scripts/run_bundle.py --verify"}), run_space),
    (Product("fiction-forks", "japan-2036-doraemon-public-tools", 42,
             {"provider": "fixture", "fixture": "fixtures/social/japan-2036-cooperation.jsonl"}), run_fiction),
    (Product("quiet-orchestrator-japan", "p0-baseline", 0,
             {"entrypoint": "npm run simulate"}), run_quiet),
]


def event_stream_sha256(events: list[dict]) -> str:
    # meta-security-sim/scripts/validate_studio_run_contract.py と同一の正規化
    payload = "".join(
        json.dumps(event, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":"), allow_nan=False) + "\n"
        for event in events
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_bundle(product: Product, result: RunResult, source_revision: str,
                 started: str, completed: str) -> dict:
    """started / completed は 2 回の実走を挟んで main() が実測した実行窓。

    Studio 契約は event 時刻が実行窓の内側にあることを要求するため、
    event の occurred_at は窓の両端だけを使い、build 時刻を混ぜない。
    """
    run_id = f"live-{product.product_id}-{started.replace(':', '').replace('-', '')}"
    output_digest = hashlib.sha256(result.output).hexdigest()
    completed_payload = {"exit_code": 0, "output_sha256": output_digest,
                         "output_bytes": len(result.output)}
    if result.product_evidence:
        completed_payload["product_evidence"] = result.product_evidence
    events = [
        {"run_id": run_id, "sequence": 0, "event_type": "run.started",
         "occurred_at": started,
         "payload": {"command": result.cmd, "runner": "cloud-autopilot/local"}},
        {"run_id": run_id, "sequence": 1, "event_type": "run.completed",
         "occurred_at": completed, "payload": completed_payload},
        {"run_id": run_id, "sequence": 2, "event_type": "determinism.checked",
         "occurred_at": completed,
         "payload": {"attempts": 2, "identical_output": True}},
    ]
    digest = event_stream_sha256(events)
    return {
        "schema": "meta-security-run-bundle/v1",
        "product_id": product.product_id,
        "run_request": {
            "run_id": run_id, "scenario_id": product.scenario_id,
            "seed": product.seed, "requested_at": started,
            "parameters": product.parameters,
        },
        "events": events,
        "replay": {
            "run_id": run_id, "product_id": product.product_id,
            "seed": product.seed, "event_count": len(events),
            "event_stream_sha256": digest, "deterministic": True,
        },
        "evidence": {
            "run_id": run_id, "product_id": product.product_id,
            "verification": "live-command", "generated_at": utc_now(),
            "source_repository": f"nexus-ai-2045/{product.product_id}",
            "event_stream_sha256": digest,
            "execution": {
                "adapter_id": ADAPTER_ID,
                "command": [str(part) for part in result.cmd],
                "exit_code": 0,
                "started_at": started,
                "completed_at": completed,
                "source_revision": source_revision,
                # 1 回目の実走の stdout。出力を file へ書く製品では path 文字列になるため、
                # 内容の束縛は run.completed の output_sha256 / product_evidence が担う
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            },
        },
    }


def validate_with_studio_schema(bundle_paths: list[Path]) -> str:
    validator = STUDIO_ROOT / "scripts" / "validate_studio_run_contract.py"
    if not validator.exists():
        return "skipped: meta-security-sim checkout not found"
    proc = subprocess.run(
        [sys.executable, str(validator), "--bundle", *map(str, bundle_paths)],
        capture_output=True, text=True, timeout=RUN_TIMEOUT_SEC,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"studio contract validation failed:\n{proc.stdout}{proc.stderr}")
    return "studio run contract PASS"


def main() -> int:
    workdir = Path.cwd()  # local runner 規約: cwd = jobs/sim-suite/output/
    bundle_dir = workdir / "studio-runs"
    bundle_dir.mkdir(exist_ok=True)
    bundle_paths: list[Path] = []
    summary: dict[str, dict] = {}
    for product, runner in PRODUCTS:
        repo = REPOS_ROOT / product.product_id
        if not repo.is_dir():
            raise RuntimeError(f"{product.product_id}: checkout が無い ({repo})。SIM_REPOS_ROOT を確認する")
        source_revision = resolve_source_revision(repo)
        started = utc_now()
        first = runner(repo, workdir, 1)
        second = runner(repo, workdir, 2)
        completed = utc_now()
        if first.output != second.output:
            raise RuntimeError(f"{product.product_id}: 2回の実行結果が一致しない (非決定論)")
        if resolve_source_revision(repo) != source_revision:
            raise RuntimeError(f"{product.product_id}: 実走中に checkout の HEAD が変わった")
        bundle = build_bundle(product, first, source_revision, started, completed)
        path = bundle_dir / f"{product.product_id}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bundle_paths.append(path)
        summary[product.product_id] = {
            "run_id": bundle["run_request"]["run_id"],
            "output_sha256": bundle["events"][1]["payload"]["output_sha256"],
            "deterministic": True,
        }
    contract = validate_with_studio_schema(bundle_paths)
    result = {"products": summary, "contract_validation": contract,
              # 評価契約 (core/evaluator.py): 決定論確認まで通った bundle 数を score にする。
              # 1 つでも欠ければここに到達しない (途中 raise) ため、空振りは score 無しで落ちる
              "score": float(len(bundle_paths))}
    (workdir / "sim_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
