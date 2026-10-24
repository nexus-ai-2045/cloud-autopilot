# local runner

クラウドが混雑・429・クォータ切れの時の fallback。および機密データを外に出さない実行先。

- 実体: Ollama / ローカル GPU (yuhitsu のローカル完結方針と同一方向)
- identity は `local` 固定 (外部名義を持たない)
- クラウド runner が `TransientError` を使い切ったら、ジョブ manifest に `fallback: local` があるものだけここへ回す (Phase 2)
