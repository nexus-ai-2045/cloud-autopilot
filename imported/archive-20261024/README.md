# 控えから取り込んだ古い版（2026-10-24）

このフォルダには、履歴を作り直す前の非公開の控えにだけ残っていた中身を、消さずに残すために置いています。

- 置き方: `<控えの枝またはタグ>/<元のパス>`。中身は控えのままです（下の「伏せたもの」を除く）。
- ここにあるファイルは実行も読み込みもされません。テストの収集からも外しています。
- 今のコードへ採り入れるかは、ファイルごとに別のPRで決めます。
- 公開側の履歴に同じ中身があるもの、行がすべて公開側にあるもの、ほかの版で行がそろうものは入れていません。
- 意図して外されていたもの（個人の情報を含む、公開側で削除済みなど）は入れていません。

## 入れたファイル

| 元のパス | 控えの枝・タグ | 置き場所 | 備考 |
|---|---|---|---|
| `.gitignore` | `main` | `main/.gitignore` |  |
| `.repo-preflight-consistency.json` | `main` | `main/.repo-preflight-consistency.json` |  |
| `README.md` | `main` | `main/README.md` |  |
| `autopilot.py` | `main` | `main/autopilot.py` |  |
| `core/api_client.py` | `main` | `main/core/api_client.py` |  |
| `core/dispatcher.py` | `main` | `main/core/dispatcher.py` |  |
| `core/ledger.py` | `main` | `main/core/ledger.py` |  |
| `jobs/kaggle-gpu-smoke/job.json` | `main` | `main/jobs/kaggle-gpu-smoke/job.json` |  |
| `jobs/kaggle-gpu-smoke/kernel/kernel-metadata.json` | `main` | `main/jobs/kaggle-gpu-smoke/kernel/kernel-metadata.json` |  |
| `jobs/kaggle-gpu-smoke/kernel/main.py` | `main` | `main/jobs/kaggle-gpu-smoke/kernel/main.py` |  |
| `jobs/local-smoke/main.py` | `main` | `main/jobs/local-smoke/main.py` |  |
| `jobs/local-smoke/output/local_run.log` | `main` | `main/jobs/local-smoke/output/local_run.log` |  |
| `jobs/local-smoke/output/local_smoke_result.json` | `main` | `main/jobs/local-smoke/output/local_smoke_result.json` |  |
| `jobs/queue/local-smoke.json` | `main` | `main/jobs/queue/local-smoke.json` |  |
| `runners/gcloud/README.md` | `main` | `main/runners/gcloud/README.md` |  |
| `runners/kaggle/run.py` | `main` | `main/runners/kaggle/run.py` |  |
| `runners/local/README.md` | `main` | `main/runners/local/README.md` |  |
| `runners/local/run.py` | `main` | `main/runners/local/run.py` |  |
| `runners/registry.py` | `main` | `main/runners/registry.py` |  |
| `tests/test_dispatcher.py` | `main` | `main/tests/test_dispatcher.py` |  |

## 伏せたもの

- なし
