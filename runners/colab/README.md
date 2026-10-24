# colab runner

GPU が要る対話実験・単発実行に使う。決まった学習ジョブは kaggle runner (定常の明示 GPU 枠) を優先
(枠の数値は root README「実行環境と無料枠」の表が正本)。

## 経路 (公式のみ、スクレイピング不使用)

Colab 公式 CLI `google-colab-cli` (2026-06 リリース) を使う。

- macOS / Linux はネイティブで叩く。**Windows のみ CLI 非対応** (公式に明記) のため WSL 経由。
  runner はまずホストの `colab` を探し、無い時だけ WSL に落ちる
- 初回セットアップ: `uv tool install google-colab-cli` → `colab auth` (ブラウザ承認が必要)。
  Windows はこれを WSL 内で行う
- Colab MCP サーバー (2026-03) もあるが、あちらは対話エージェント向け。スクリプト自走には CLI が適する

## 名義

- `config.local.json` にエイリアス `colab-main` として自分の Google アカウントを登録する
- `colab auth` で承認したアカウントと manifest の identity が一致しているかは、
  セットアップ時に人間が確認する (CLI からは読めない)

## 制約

- 無料枠の数値 (セッション上限等) は root README「実行環境と無料枠」の表が正本 (ここに再掲しない)
- リソース保証なし・アイドル切断あり
- **常駐やスケジュール実行には使わない** (向いていない)。単発実行のみ
