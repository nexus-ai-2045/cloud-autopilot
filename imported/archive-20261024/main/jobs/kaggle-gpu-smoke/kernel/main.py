# GPU smoke: 割当 GPU を実測して結果を出力に残す (canary 1-step 相当)
import json
import subprocess
from datetime import datetime, timezone

result = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "gpu": None}
try:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=60,
    )
    result["gpu"] = out.stdout.strip() or out.stderr.strip()
except Exception as e:  # GPU なしでも証跡は残す (fail-closed)
    result["gpu"] = f"error: {e}"

print(json.dumps(result, ensure_ascii=False))
with open("gpu_smoke_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False)
