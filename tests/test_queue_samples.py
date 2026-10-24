"""同梱 queue の規約 (docs/adr/0001): clean clone + config.local.json だけで走るジョブに限る。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.manifest import JobManifest

QUEUE = Path(__file__).resolve().parent.parent / "jobs" / "queue"


def test_bundled_queue_jobs_are_environment_independent():
    manifests = sorted(QUEUE.glob("*.json"))
    assert manifests, "同梱 queue が空"
    for path in manifests:
        job = JobManifest.load(path)
        assert job.runner == "local", f"{path.name}: 同梱 queue はクラウド名義を前提にしない"
        assert job.identity == "local"
        target = (path.parent / job.entrypoint).resolve()
        assert target.exists(), f"{path.name}: entrypoint が repo 内に無い"


def test_external_dependency_jobs_are_not_bundled_in_queue():
    """過去バグ: sim-suite (外部 4 製品 checkout + npm 必須) が queue に同梱され、
    README 手順 2 が clean clone で exit 1 になっていた。"""
    assert not (QUEUE / "sim-suite.json").exists()
    assert (QUEUE.parent / "sim-suite" / "job.json").exists()
