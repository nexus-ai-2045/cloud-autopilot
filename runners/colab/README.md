# colab runner

GPU が要る対話実験・単発実行に使う。決まった学習ジョブは kaggle runner (週 30h の明示枠) を優先。

## 経路 (公式のみ、スクレイピング不使用)

Colab 公式 CLI `google-colab-cli` (2026-06 リリース) を使う。

- **Windows 非対応** (公式に明記) のため、Windows では WSL 経由で叩く
- 初回セットアップ: WSL 内で `uv tool install google-colab-cli` → `colab auth` (ブラウザ承認が必要)
- Colab MCP サーバー (2026-03) もあるが、あちらは対話エージェント向け。スクリプト自走には CLI が適する

## 名義

- `config.local.json` にエイリアス `colab-main` として自分の Google アカウントを登録する
- `colab auth` で承認したアカウントと manifest の identity が一致しているかは、
  セットアップ時に人間が確認する (CLI からは読めない)

## 制約 (2026-08 時点の無料枠)

- リソース保証なし・最長 12 時間・アイドル切断あり
- **常駐やスケジュール実行には使わない** (向いていない)。単発実行のみ
