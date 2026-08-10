from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from user_data.strategies.CK_Trend_1m import CK_Trend_1m


def analyzed_dataframe(side: str) -> pd.DataFrame:
    rows = 25
    open_ = np.full(rows, 100.0)
    close = np.full(rows, 100.0)
    bid = np.full(rows, 50.0)
    ask = np.full(rows, 50.0)
    delta = np.zeros(rows)

    if side == "long":
        close[-1] = 101.0
        bid[-3:] = [40.0, 40.0, 30.0]
        ask[-3:] = [60.0, 60.0, 70.0]
        delta[-3:] = [20.0, 20.0, 40.0]
    else:
        close[-1] = 99.0
        bid[-3:] = [60.0, 60.0, 70.0]
        ask[-3:] = [40.0, 40.0, 30.0]
        delta[-3:] = [-20.0, -20.0, -40.0]

    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 1.0,
            "low": np.minimum(open_, close) - 1.0,
            "close": close,
            "volume": np.full(rows, 100.0),
            "bid": bid,
            "ask": ask,
            "delta": delta,
            "total_trades": np.full(rows, 150),
        }
    )


@pytest.mark.parametrize(
    ("side", "entry_column", "tag"),
    [
        ("long", "enter_long", "| 订单流确认：主动买盘入场做多 |"),  # noqa: RUF001
        ("short", "enter_short", "| 订单流确认：主动卖盘入场做空 |"),  # noqa: RUF001
    ],
)
def test_orderflow_entry(monkeypatch, side, entry_column, tag) -> None:
    strategy = object.__new__(CK_Trend_1m)
    strategy.slow_period = 2
    strategy.body_atr_lookback = 2
    monkeypatch.setattr(
        "user_data.strategies.CK_Trend_1m.ta.ATR",
        lambda dataframe, timeperiod: pd.Series(np.ones(len(dataframe))),
    )
    monkeypatch.setattr(
        "user_data.strategies.CK_Trend_1m.ta.EMA",
        lambda dataframe, timeperiod: pd.Series(np.ones(len(dataframe))),
    )

    result = strategy.populate_indicators(analyzed_dataframe(side), {})
    result = strategy.populate_entry_trend(result, {})

    assert result[entry_column].iat[-1] == 1
    assert result["enter_tag"].iat[-1] == tag


def test_missing_orderflow_data_never_enters(monkeypatch) -> None:
    strategy = object.__new__(CK_Trend_1m)
    strategy.slow_period = 2
    strategy.body_atr_lookback = 2
    dataframe = analyzed_dataframe("long").drop(
        columns=["bid", "ask", "delta", "total_trades"]
    )
    monkeypatch.setattr(
        "user_data.strategies.CK_Trend_1m.ta.ATR",
        lambda frame, timeperiod: pd.Series(np.ones(len(frame))),
    )
    monkeypatch.setattr(
        "user_data.strategies.CK_Trend_1m.ta.EMA",
        lambda frame, timeperiod: pd.Series(np.ones(len(frame))),
    )

    result = strategy.populate_indicators(dataframe, {})
    result = strategy.populate_entry_trend(result, {})

    assert not result["orderflow_long_entry"].any()
    assert not result["orderflow_short_entry"].any()
    assert not result["enter_long"].fillna(0).eq(1).any()
    assert not result["enter_short"].fillna(0).eq(1).any()


@pytest.mark.parametrize(
    ("is_short", "expected_stop_rate"),
    [(False, 96.0), (True, 104.0)],
)
def test_custom_stoploss_is_fixed_at_four_entry_atr(is_short, expected_stop_rate) -> None:
    strategy = object.__new__(CK_Trend_1m)
    strategy.dp = MagicMock()
    strategy.dp.get_analyzed_dataframe.return_value = (
        pd.DataFrame({"ATR": [1.0]}),
        None,
    )

    custom_data = {}
    trade = MagicMock()
    trade.open_rate = 100.0
    trade.is_short = is_short
    trade.leverage = 10.0
    trade.get_custom_data.side_effect = custom_data.get
    trade.set_custom_data.side_effect = custom_data.__setitem__

    first_result = strategy.custom_stoploss(
        pair="ETH/USDT:USDT",
        trade=trade,
        current_time=None,
        current_rate=100.0,
        current_profit=0.0,
        after_fill=True,
    )
    strategy.dp.get_analyzed_dataframe.return_value = (
        pd.DataFrame({"ATR": [9.0]}),
        None,
    )
    second_result = strategy.custom_stoploss(
        pair="ETH/USDT:USDT",
        trade=trade,
        current_time=None,
        current_rate=100.0,
        current_profit=0.0,
        after_fill=False,
    )

    assert first_result == pytest.approx(0.4)
    assert second_result == pytest.approx(0.4)
    assert custom_data[strategy.entry_atr_custom_data_key] == 1.0
    calculated_stop_rate = (
        100.0 * (1 + first_result / trade.leverage)
        if is_short
        else 100.0 * (1 - first_result / trade.leverage)
    )
    assert calculated_stop_rate == pytest.approx(expected_stop_rate)


def test_leverage_uses_exchange_maximum() -> None:
    strategy = object.__new__(CK_Trend_1m)

    result = strategy.leverage(
        pair="ETH/USDT:USDT",
        current_time=None,
        current_rate=100.0,
        proposed_leverage=1.0,
        max_leverage=150.0,
        entry_tag=None,
        side="long",
    )

    assert result == 150.0


def test_reversal_exits_are_temporarily_disabled() -> None:
    strategy = object.__new__(CK_Trend_1m)
    dataframe = pd.DataFrame(
        {
            "body_atr": [-3.0, 3.0],
            "two_bearish_large_body": [True, False],
            "two_bullish_large_body": [False, True],
            "three_bearish_large_body": [True, False],
            "three_bullish_large_body": [False, True],
        }
    )

    result = strategy.populate_exit_trend(dataframe, {})

    assert not result["exit_long"].any()
    assert not result["exit_short"].any()
    assert strategy.custom_exit(
        pair="ETH/USDT:USDT",
        trade=MagicMock(),
        current_time=None,
        current_rate=100.0,
        current_profit=0.0,
    ) is None
