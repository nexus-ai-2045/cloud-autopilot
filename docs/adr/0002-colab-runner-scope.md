# ADR-0002: colab runner の責務範囲 (成果物回収は対象外)

- 状態: 採択 (2026-09-18)
- 関連: runners/registry.py `colab_run`, runners/colab/README.md, README「評価契約」

## 背景

colab runner は Colab 公式 CLI (`colab exec`) を呼び、その exit code を返すだけで、
`<entrypoint>/output/` の生成も `sim_result.json` の回収も行わない。一方、評価契約 (score) は
`output/sim_result.json` を読む。したがって colab ジョブに `score_required: true` を付けると
常に「score 無し」の契約違反となる。監査で、この不整合がどの文書にも書かれていないことが確定した。

## 決定

- 現時点の colab runner の責務は「実行して exit code を返す」まで。成果物回収と評価契約は**対象外**
- `score_required` を colab ジョブに付けた場合に契約違反で止まるのは**意図した fail-closed** であり、
  バグではない。README「実行環境と無料枠」表と「評価契約」節に明記する
- 回収を実装する条件: Colab CLI が実行結果ファイルを取得する手段を**一次情報 (公式 docs) で確認**
  してから。推測で `output/` を作らない

## 結果

- colab は単発 GPU 実験の起動用途に限定され、自動改善ループの実行環境は当面 kaggle と local
- 「証跡を持ち帰る」責務は kaggle / local で満たし、colab は例外として文書化する

## 却下した代替案

- **stdout から score を拾う**: score 契約の正本は `sim_result.json` であり、経路ごとに契約を変えると
  評価器が runner 依存になる
