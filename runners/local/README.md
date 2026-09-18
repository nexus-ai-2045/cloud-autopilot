# local runner

クラウドが混雑・429・クォータ切れの時の fallback。および機密データを外に出さない実行先。

- entrypoint (Python スクリプト) をこのマシンでそのまま実行し、出力を `<entrypoint>/output/` に置く
- identity は `local` 固定 (外部名義を持たないため、名義取り違えが構造上起きない)
- クラウド runner が失敗したジョブのうち、manifest に `"fallback": ["local"]` があるものだけここへ回る
- fallback 先が local だけなのは意図的: 外部名義への自動振替は名義事故のもと
- fallback 専用ではなく主 runner としても使う (同梱 queue の `sim-smoke-local` がその例)。
  そのため `config.local.json` には `local` エイリアス (`config.example.json` に同梱) が必要
