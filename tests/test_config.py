"""core/config.py (名義のローカル設定) のテスト。

設計方針 (README 参照):
- 名義・アカウント名は repo に置かず config.local.json (gitignore 済) から読む
- 未設定なら黙って動かず、何が足りないかを言って停止する (fail-closed)
- エイリアスは runner に束縛され、manifest の runner と不一致なら停止
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import ConfigError, IdentityBook


def _book(**identities) -> IdentityBook:
    return IdentityBook.from_dict({"identities": identities})


def test_load_missing_file_fails_closed_with_recovery_hint(tmp_path):
    """設定ファイルが無いとき、黙って動かず復旧手順を言って止まる。"""
    with pytest.raises(ConfigError) as e:
        IdentityBook.load(tmp_path / "config.local.json")
    msg = str(e.value)
    assert "config.local.json" in msg
    assert "config.example.json" in msg  # 復旧手順 (cp 元) を必ず示す


def test_load_roundtrip(tmp_path):
    path = tmp_path / "config.local.json"
    path.write_text(
        json.dumps({"identities": {"kaggle-main": {"runner": "kaggle", "account": "someone"}}}),
        encoding="utf-8",
    )
    book = IdentityBook.load(path)
    ident = book.resolve("kaggle-main", "kaggle")
    assert ident.account == "someone"


def test_resolve_unknown_alias_lists_registered():
    book = _book(**{"kaggle-main": {"runner": "kaggle", "account": "someone"}})
    with pytest.raises(ConfigError, match="未登録"):
        book.resolve("colab-main", "colab")


def test_resolve_runner_mismatch_stops():
    """kaggle 用の名義を colab ジョブに使おうとしたら止まる (取り違え防止)。"""
    book = _book(**{"kaggle-main": {"runner": "kaggle", "account": "someone"}})
    with pytest.raises(ConfigError, match="取り違え"):
        book.resolve("kaggle-main", "colab")


def test_resolve_placeholder_account_rejected():
    """config.example.json のダミー値のまま実行しようとしたら止まる。"""
    book = _book(**{"kaggle-main": {"runner": "kaggle", "account": "your-kaggle-username"}})
    with pytest.raises(ConfigError, match="プレースホルダ"):
        book.resolve("kaggle-main", "kaggle")


def test_resolve_local_is_exempt_from_placeholder_check():
    book = _book(local={"runner": "local", "account": "local"})
    assert book.resolve("local", "local").account == "local"


def test_from_dict_requires_identities_section():
    with pytest.raises(ConfigError, match="identities"):
        IdentityBook.from_dict({})


def test_from_dict_requires_runner_and_account():
    with pytest.raises(ConfigError, match="runner / account"):
        IdentityBook.from_dict({"identities": {"x": {"runner": "kaggle"}}})


def test_example_config_is_loadable_but_not_runnable():
    """config.example.json は形式として正しいが、そのままでは実行できない (ダミー値検知)。"""
    example = Path(__file__).resolve().parent.parent / "config.example.json"
    book = IdentityBook.load(example)
    with pytest.raises(ConfigError, match="プレースホルダ"):
        book.resolve("kaggle-main", "kaggle")
