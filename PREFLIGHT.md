# PREFLIGHT

この repo は公開・push の前に [repo-preflight](https://github.com/nexus-ai-2045/repo-preflight)
で機械検査します。

## 検査項目 (公開時に pass を確認済み)

- secret 候補スキャン: 0 件
- 個人パス・名義スキャン: 0 件 (アカウント名は `config.local.json` に外出しする設計)
- 全履歴の個人識別子 grep: 0 件 (initial commit のみの fresh history)
- 必須文書: README / LICENSE / SECURITY / CONTRIBUTING / PREFLIGHT
- clean worktree + テスト緑

## 再実行

```bash
python <repo-preflight>/run_preflight.py --repo . --intent push --human
```

整合性検査の宣言は [.repo-preflight-consistency.json](.repo-preflight-consistency.json)
(shadow mode) にあります。
