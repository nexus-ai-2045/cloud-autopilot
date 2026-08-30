"""名義 (identity) のローカル設定。

アカウント名・メールアドレスは repo に置かない。config.local.json (gitignore 済み)
から読み、manifest にはエイリアス (例: kaggle-main) だけを書く。
未設定のまま実行したら黙って動かず、何が足りないかを言って停止する (fail-closed)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CONFIG_LOCAL = "config.local.json"
CONFIG_EXAMPLE = "config.example.json"

# config.example.json が読めない時だけ使う予備の目印 (通常経路は完全一致判定)
_PLACEHOLDER_MARKS = ("your-", "example.com")


def _load_placeholder_accounts(path: Path) -> frozenset[str] | None:
    """ダミー値の正本 = config.example.json の account 値 (SSOT。ここに値を再掲しない)。

    完全一致で判定する。部分文字列判定だと実アカウント名が偶然 'your-' 等を
    含むだけで誤拒否するため。読めない・構造が想定外・non-local が 1 つも無い場合は
    None を返し、呼び手を予備判定に落とす (空集合を正とみなすと fail-open になる)。
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ids = raw.get("identities") if isinstance(raw, dict) else None
    if not isinstance(ids, dict):
        return None
    accounts = frozenset(
        entry["account"]
        for entry in ids.values()
        if isinstance(entry, dict) and entry.get("account") and entry.get("runner") != "local"
    )
    return accounts or None


@lru_cache(maxsize=1)
def _placeholder_accounts() -> frozenset[str] | None:
    return _load_placeholder_accounts(Path(__file__).resolve().parent.parent / CONFIG_EXAMPLE)


def _is_placeholder(account: str) -> bool:
    accounts = _placeholder_accounts()
    if accounts is not None:
        return account in accounts
    # example が無い/壊れている環境でも fail-open にしない (従来の部分一致で拾う)
    return any(m in account for m in _PLACEHOLDER_MARKS)


class ConfigError(ValueError):
    """設定エラー。何が足りないか・どう直すかを必ずメッセージに含める。"""


@dataclass(frozen=True)
class Identity:
    """エイリアス 1 つ分の解決結果。runner に束縛される (取り違え防止)。"""

    alias: str
    runner: str
    account: str


class IdentityBook:
    """エイリアス → Identity の名義帳。config.local.json が唯一の供給源。"""

    def __init__(self, identities: dict[str, Identity]) -> None:
        self._identities = dict(identities)

    @classmethod
    def from_dict(cls, raw: dict, *, source: str = CONFIG_LOCAL) -> "IdentityBook":
        ids = raw.get("identities")
        if not isinstance(ids, dict) or not ids:
            raise ConfigError(
                f"{source} に identities セクションが無い。{CONFIG_EXAMPLE} の形式で名義を登録する"
            )
        book: dict[str, Identity] = {}
        for alias, entry in ids.items():
            if not isinstance(entry, dict) or not entry.get("runner") or not entry.get("account"):
                raise ConfigError(f"{source} の名義 '{alias}' に runner / account が無い")
            book[alias] = Identity(alias=alias, runner=entry["runner"], account=entry["account"])
        return cls(book)

    @classmethod
    def load(cls, path: Path | str) -> "IdentityBook":
        path = Path(path)
        if not path.exists():
            raise ConfigError(
                f"{path.name} が無い。名義はローカル設定から読む設計で、repo には置かない。\n"
                f"  1. cp {CONFIG_EXAMPLE} {path.name}\n"
                f"  2. 自分のアカウント名を記入する ({path.name} は gitignore 済みで commit されない)"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(f"{path.name} が JSON として読めない: {e}") from e
        return cls.from_dict(raw, source=path.name)

    def resolve(self, alias: str, runner: str) -> Identity:
        """manifest の (identity, runner) 宣言を検証して実名義を返す。

        1 つでも合わなければ実行前に止める。runner まで到達させない。
        """
        ident = self._identities.get(alias)
        if ident is None:
            raise ConfigError(
                f"名義 '{alias}' は未登録 (登録済: {sorted(self._identities)})。"
                f"{CONFIG_LOCAL} の identities に追加する"
            )
        if ident.runner != runner:
            raise ConfigError(
                f"名義 '{alias}' は runner '{ident.runner}' 用だが、manifest の runner は '{runner}'。"
                "名義の取り違え防止のため停止"
            )
        if ident.runner != "local" and _is_placeholder(ident.account):
            raise ConfigError(
                f"名義 '{alias}' の account '{ident.account}' がプレースホルダのまま。"
                f"{CONFIG_LOCAL} に実際のアカウント名を記入する"
            )
        return ident
