# kaggle runner

決まったシミュレーションジョブの主力実行先。無料 GPU の明示枠がある。

## 前提 (各自のローカル設定)

1. Kaggle アカウント (GPU 利用の認証要件は root README「実行環境と無料枠」の表が正本)
2. API トークン: Kaggle の Settings → API → Create New Token → `~/.kaggle/kaggle.json` に配置
3. `pip install kaggle`
4. `config.local.json` にエイリアス `kaggle-main` として自分のユーザー名を登録

## 動作

1. manifest の `entrypoint` ディレクトリに `kernel-metadata.json` を**実行時に生成**する
   (アカウント名は config.local.json から注入。repo にはアカウント名を置かない)
2. `kaggle kernels push` で private kernel として投稿 (internet 無効が既定)
3. 30 秒間隔で完走を polling (上限 20 分)
4. 完走したら `kernels output` で成果物を `<entrypoint>/output/` に回収し、台帳に記録

## 制約

- 無料枠の数値 (GPU 時間・セッション上限・アカウント規約) は
  root README「実行環境と無料枠」の表が正本 (ここに再掲しない)
- 429/5xx は共通バックオフで再試行し、台帳に記録する
  (具体値は `core/api_client.py` 冒頭の定数が正本)
