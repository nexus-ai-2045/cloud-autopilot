# gcloud runner

## 既存資産 (実測 2026-08-25)

- project `nexus-ai-2045` に Cloud Run サービス `automata-watch` が**現役稼働中** (asia-northeast1)
- GCS bucket 5+ (automata-watch / cloud-observation-hub / codex-changelog-monitor 等)
- 名義: 個人の Google アカウント (環境変数 `CLOUD_AUTOPILOT_GCLOUD_IDENTITY` で指定) (gcloud CLI auth ACTIVE)

## 移植元

yuhitsu-shohyo の `cloud_orchestrator` / `cloud_control_api` / `cloud_coding_agent` (yuhitsu 本体はローカル完結方針に転換したため orphan 化した機構)。
retry 方針 (429/5xx のみ・5s→60s×2・3回) は core/api_client.py に反映済み。

## 無料枠の使い方 (2026-08 再確認済)

- **e2-micro 1 台 恒久無料** (US 3 リージョン限定: us-west1/central1/east1) → 司令塔 (キュー・台帳・cron) 用。Phase 3
- **Cloud Run 恒久無料枠** (月200万 req / 18万 vCPU 秒) → ジョブ起動・webhook 受け口
- Vertex 等の課金系は**予算上限を宣言してから** (yuhitsu-shohyo で通常300/絶対500 USD の前例)
