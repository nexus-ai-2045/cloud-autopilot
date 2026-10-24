# 自走ループ E2E 用の最小ジョブ: 実行時刻を出力に残すだけ
import json
from datetime import datetime, timezone

result = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "msg": "local-smoke ok"}
print(json.dumps(result, ensure_ascii=False))
with open("local_smoke_result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False)
