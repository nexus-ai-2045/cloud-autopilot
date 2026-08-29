# コントリビューションガイド

`cloud-autopilot` の改善に関心を持っていただき、ありがとうございます。

## ローカルセットアップ

```bash
cp config.example.json config.local.json   # 自分のアカウント名を記入
python -m pytest tests/ -q
```

Windows で共有 tmp の権限エラーが出る場合:

```bash
python -m pytest tests -q -p no:cacheprovider --basetemp=./.pytest-tmp
```

## 開発ルール

- **名義・アカウント名・メールアドレスを repo に入れない**。manifest にはエイリアスのみ
- **fail-closed を守る**: 設定不備で黙って動かない。何が足りないかを言って停止する
- 再試行してよいのは HTTP 429/500/502/503/504 のみ。「とりあえず再試行」を追加しない
- 挙動の変更にはテストを付ける。検知系を足したら、既知のバグを注入して落ちることを確認する
- サンプルジョブはシード固定で再現可能に保つ

## PR の前に

```bash
python -m pytest tests/ -q
```

全テスト緑と、追加・変更した挙動のテストが揃っていることを確認してください。
