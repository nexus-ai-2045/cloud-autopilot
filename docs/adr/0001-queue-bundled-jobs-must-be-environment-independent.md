# ADR-0001: 同梱 queue のジョブは環境非依存に限る

- 状態: 採択 (2026-09-18)
- 関連: README「ジョブの書き方」, tests/test_queue_samples.py, tests/test_cli_e2e.py

## 背景

README クイックスタート手順 2「まずローカルで動作確認 (クラウド不要)」は `python autopilot.py queue` を
実行する。完成度監査で clean clone + `config.local.json` だけの環境で実測したところ、同梱されていた
`jobs/queue/sim-suite.json` が外部 4 製品の checkout と npm を前提にしていたため `failed` となり、
queue 全体が exit 1 になった。failed は終端状態なので、後から前提を揃えても
`data/queue_state.json` を消さない限り再走しない。「README だけで他人が自分のアカウントで動かせる」
という repo の完了条件が、同梱ジョブ 1 つで破れていた。

## 決定

`jobs/queue/` に同梱する manifest は、**clean clone と `config.local.json` だけで完走するもの**に限る。
外部 checkout・外部 CLI・課金・クラウド名義を前提とするジョブは `jobs/<name>/job.json` に置き、
`python autopilot.py run jobs/<name>/job.json` で明示的に実行する。
この規約は `tests/test_queue_samples.py` と `tests/test_cli_e2e.py` が機械検査する。

## 結果

- clean clone で README 手順 2 が exit 0 になる
- sim-suite は `jobs/sim-suite/job.json` へ移動した
- 利用者が自分の queue に外部依存ジョブを置くことは妨げない (同梱物の規約であって機能制限ではない)

## 却下した代替案

- **queue 側で前提未満のジョブを skipped 扱いにする**: 「失敗を黙殺しない」設計原則と衝突する。
  前提が無いのは利用者が知るべき事実であり、隠すべきではない
- **README に「sim-suite は失敗して正常」と注記する**: 初見の利用者に exit 1 を「正常」と読ませるのは、
  成功と失敗の区別 (脅威モデル a) を自ら曖昧にする
