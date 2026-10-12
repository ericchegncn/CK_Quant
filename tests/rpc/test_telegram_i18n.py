# pragma pylint: disable=missing-docstring, protected-access, unused-argument

"""
End-to-end checks that the Telegram bot really renders its messages in the
configured language (config default + /language per chat override).
"""

import json
import re
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from freqtrade.enums import ExitType, RPCMessageType
from freqtrade.rpc.i18n import SUPPORTED_LOCALES
from freqtrade.util.datetime_helpers import dt_now
from tests.rpc.test_rpc_telegram import (  # noqa: F401 - fixtures reused from the upstream tests
    default_conf as default_conf,
    get_telegram_testobject,
    update as update,
)

CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff\uac00-\ud7af]")


@pytest.fixture(autouse=True)
def mock_exchange_loop(mocker):
    mocker.patch("freqtrade.exchange.exchange.Exchange._init_async_loop")


def _entry_msg() -> dict:
    return {
        "type": RPCMessageType.ENTRY,
        "enter_tag": "long_signal_01",
        "trade_id": 1,
        "exchange": "Binance",
        "pair": "ETH/BTC",
        "leverage": 1.0,
        "open_rate": 1.099e-05,
        "order_type": "limit",
        "direction": "Long",
        "sub_trade": False,
        "stake_amount": 0.01465333,
        "stake_amount_fiat": 0.0,
        "stake_currency": "BTC",
        "quote_currency": "BTC",
        "base_currency": "ETH",
        "fiat_currency": None,
        "current_rate": 1.099e-05,
        "amount": 1333.3333333333335,
        "open_date": dt_now() - timedelta(hours=1),
    }


def _exit_msg() -> dict:
    return {
        "type": RPCMessageType.EXIT,
        "trade_id": 1,
        "exchange": "Binance",
        "pair": "ETH/BTC",
        "gain": "profit",
        "leverage": 1.0,
        "limit": 1.173e-05,
        "order_rate": 1.173e-05,
        "amount": 91.07468123,
        "order_type": "limit",
        "open_rate": 1.098e-05,
        "current_rate": 1.173e-05,
        "direction": "Long",
        "profit_amount": 6.314e-05,
        "profit_ratio": 0.0629778,
        "stake_currency": "BTC",
        "quote_currency": "BTC",
        "base_currency": "ETH",
        "fiat_currency": "USD",
        "enter_tag": "long_signal_01",
        "exit_reason": ExitType.ROI.value,
        "open_date": dt_now() - timedelta(hours=1),
        "close_date": dt_now(),
        "close_rate": 1.173e-05,
        "stake_amount": 0.0009999999999054,
        "sub_trade": False,
        "cumulative_profit": 0.0,
        "is_final_exit": False,
        "final_profit_ratio": None,
    }


def _render(default_conf, mocker, language: str, msg: dict | None = None) -> str:
    default_conf["telegram"]["language"] = language
    telegram, _, msg_mock = get_telegram_testobject(mocker, default_conf)
    telegram.send_msg(msg or _entry_msg())
    return msg_mock.call_args[0][0]


def test_entry_notification_matches_config_language(default_conf, mocker) -> None:
    """English is the default and is byte-identical to the catalogue wording."""
    english = _render(default_conf, mocker, "en")
    assert "*Pair:* `ETH/BTC`" in english
    assert "New Trade" in english
    assert not CJK_RE.search(english)

    chinese = _render(default_conf, mocker, "zh-CN")
    assert CJK_RE.search(chinese)
    assert "交易对" in chinese
    assert "*Pair:*" not in chinese
    # same structure, data passed through untouched
    assert len(chinese.splitlines()) == len(english.splitlines())
    assert "ETH/BTC" in chinese
    assert "1333.33333333" in chinese  # round_value(amount, 8)


def test_exit_notification_is_localized(default_conf, mocker) -> None:
    english = _render(default_conf, mocker, "en", _exit_msg())
    assert "*Exit Reason:* `roi`" in english

    chinese = _render(default_conf, mocker, "zh-CN", _exit_msg())
    assert CJK_RE.search(chinese)
    assert "出场原因" in chinese
    # an exit reason is data - it must not be translated
    assert "`roi`" in chinese


@pytest.mark.parametrize("language", [loc for loc in SUPPORTED_LOCALES if loc != "en"])
def test_every_shipped_locale_renders(default_conf, mocker, language) -> None:
    """Each shipped locale must produce a translated (non-English) entry message."""
    english = _render(default_conf, mocker, "en")
    translated = _render(default_conf, mocker, language)
    assert "*Pair:*" not in translated
    assert "ETH/BTC" in translated
    assert len(translated.splitlines()) == len(english.splitlines())


async def test_language_command_lists_and_switches(default_conf, update, mocker, tmp_path) -> None:
    default_conf["user_data_dir"] = tmp_path
    telegram, _, msg_mock = get_telegram_testobject(mocker, default_conf)
    context = MagicMock()
    context.args = []

    await telegram._language(update=update, context=context)
    listing = msg_mock.call_args[0][0]
    for code in SUPPORTED_LOCALES:
        assert code in listing
    assert "English" in listing  # native names are always shown

    context.args = ["de"]
    await telegram._language(update=update, context=context)
    assert telegram._i18n.locale_for(1235) == "de"
    saved = json.loads((tmp_path / "bot_languages.json").read_text(encoding="utf-8"))
    assert saved == {"chats": {"1235": "de"}}

    # aliases resolve, unknown values are rejected and keep the current language
    context.args = ["zh"]
    await telegram._language(update=update, context=context)
    assert telegram._i18n.locale_for(1235) == "zh-CN"
    context.args = ["klingon"]
    await telegram._language(update=update, context=context)
    assert "klingon" in msg_mock.call_args[0][0]
    assert telegram._i18n.locale_for(1235) == "zh-CN"


async def test_rpc_errors_use_configured_language(default_conf, update, mocker) -> None:
    """Errors raised by the RPC layer are localized too (/status without trades)."""
    default_conf["telegram"]["language"] = "zh-CN"
    telegram, _, msg_mock = get_telegram_testobject(mocker, default_conf)
    context = MagicMock()
    context.args = []

    await telegram._status(update=update, context=context)
    message = msg_mock.call_args[0][0]
    assert CJK_RE.search(message)
    assert "no active trade" not in message
