import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from freqtrade.rpc.api_server.api_ck_quant_admin import (
    REDACTED,
    _admin_market_rows,
    _atomic_write,
    _redact_config,
    _restore_secrets,
    _save,
    _strategy_path,
    _validate_strategy,
)


def make_strategy_rpc(strategy_path: Path, strategy_name: str = "ManagedStrategy") -> MagicMock:
    strategy = MagicMock()
    strategy.__file__ = str(strategy_path)
    strategy.get_strategy_name.return_value = strategy_name
    rpc = MagicMock()
    rpc._freqtrade.strategy = strategy
    return rpc


def test_redaction_and_secret_restore() -> None:
    original = {
        "exchange": {"name": "binance", "key": "exchange-key", "secret": "secret"},
        "api_server": {"username": "operator", "password": "password", "ws_token": "ws"},
        "max_open_trades": 10,
    }

    redacted = _redact_config(original)

    assert redacted["exchange"]["key"] == REDACTED
    assert redacted["exchange"]["secret"] == REDACTED
    assert redacted["api_server"]["password"] == REDACTED
    assert redacted["api_server"]["username"] == "operator"
    assert original["exchange"]["key"] == "exchange-key"

    redacted["max_open_trades"] = 20
    restored = _restore_secrets(redacted, original)
    assert restored["exchange"]["key"] == "exchange-key"
    assert restored["api_server"]["password"] == "password"
    assert restored["max_open_trades"] == 20


def test_admin_market_rows_filters_normalizes_and_sorts() -> None:
    exchange = MagicMock()
    exchange.get_markets.return_value = {
        "ETH/USDT:USDT": {"base": "ETH", "quote": "USDT"},
        "BTC/USDT:USDT": {"base": "BTC", "quote": "USDT"},
        "NEW/USDT:USDT": {"base": "NEW", "quote": "USDT"},
    }
    exchange.get_tickers.return_value = {
        "BTC/USDT:USDT": {
            "last": 60000,
            "quoteVolume": "2500000000",
            "percentage": 1.25,
        },
        "ETH/USDT:USDT": {
            "last": "3000.5",
            "quoteVolume": 1200000000,
            "percentage": "-2.5",
        },
        "NEW/USDT:USDT": {
            "last": None,
            "quoteVolume": float("nan"),
            "percentage": None,
        },
    }

    rows = _admin_market_rows(exchange, {"stake_currency": "USDT"})

    assert [row.pair for row in rows] == [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "NEW/USDT:USDT",
    ]
    assert rows[0].quote_volume == 2500000000
    assert rows[1].last == 3000.5
    assert rows[1].percentage == -2.5
    assert rows[2].quote_volume is None
    exchange.get_markets.assert_called_once_with(
        quote_currencies=["USDT"], tradable_only=True, active_only=True
    )
    exchange.get_tickers.assert_called_once_with(cached=True)


def test_atomic_write_preserves_permissions(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)

    _atomic_write(target, "new\n")

    assert target.read_text(encoding="utf-8") == "new\n"
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o640


def test_strategy_validation_and_managed_path(tmp_path: Path) -> None:
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    strategy_path = strategy_dir / "ManagedStrategy.py"
    strategy_path.write_text("class ManagedStrategy: pass\n", encoding="utf-8")
    config = {"user_data_dir": tmp_path}
    rpc = make_strategy_rpc(strategy_path)

    assert _strategy_path(config, rpc) == strategy_path
    assert (
        _validate_strategy("class ManagedStrategy:\n    pass", config, rpc)
        == "class ManagedStrategy:\n    pass\n"
    )

    with pytest.raises(HTTPException, match="must remain"):
        _validate_strategy("class RenamedStrategy:\n    pass\n", config, rpc)
    with pytest.raises(HTTPException, match="Invalid Python"):
        _validate_strategy("class ManagedStrategy(:\n", config, rpc)


def test_strategy_save_backup_conflict_and_reload(tmp_path: Path) -> None:
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    strategy_path = strategy_dir / "ManagedStrategy.py"
    old_source = "class ManagedStrategy:\n    value = 1\n"
    new_source = "class ManagedStrategy:\n    value = 2\n"
    strategy_path.write_text(old_source, encoding="utf-8")
    config = {"user_data_dir": tmp_path}
    rpc = make_strategy_rpc(strategy_path)

    from freqtrade.rpc.api_server.api_ck_quant_admin import _revision

    result = _save(
        kind="strategy",
        path=strategy_path,
        source=new_source,
        expected_revision=_revision(old_source),
        apply=True,
        config=config,
        rpc=rpc,
    )

    assert strategy_path.read_text(encoding="utf-8") == new_source
    assert result.reload_requested is True
    assert (tmp_path / "backups" / "ck_quant_admin" / result.backup_id).read_text(
        encoding="utf-8"
    ) == old_source
    rpc._rpc_reload_config.assert_called_once_with()
    assert (tmp_path / "logs" / "ck_quant_admin_audit.jsonl").is_file()

    with pytest.raises(HTTPException, match="changed after"):
        _save(
            kind="strategy",
            path=strategy_path,
            source=old_source,
            expected_revision=_revision(old_source),
            apply=False,
            config=config,
            rpc=rpc,
        )


def test_failed_reload_automatically_restores_strategy(tmp_path: Path) -> None:
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    strategy_path = strategy_dir / "ManagedStrategy.py"
    old_source = "class ManagedStrategy:\n    value = 1\n"
    strategy_path.write_text(old_source, encoding="utf-8")
    config = {"user_data_dir": tmp_path}
    rpc = make_strategy_rpc(strategy_path)
    rpc._rpc_reload_config.side_effect = [RuntimeError("reload failed"), None]

    from freqtrade.rpc.api_server.api_ck_quant_admin import _revision

    with pytest.raises(HTTPException, match="restored automatically"):
        _save(
            kind="strategy",
            path=strategy_path,
            source="class ManagedStrategy:\n    value = 2\n",
            expected_revision=_revision(old_source),
            apply=True,
            config=config,
            rpc=rpc,
        )

    assert strategy_path.read_text(encoding="utf-8") == old_source
    assert rpc._rpc_reload_config.call_count == 2
