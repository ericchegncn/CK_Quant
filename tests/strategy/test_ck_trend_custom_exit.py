from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from user_data.strategies.CK_Trend import CK_Trend


def custom_exit(body_atr: list[float], *, is_short: bool, current_profit: float):
    strategy = object.__new__(CK_Trend)
    dataframe = pd.DataFrame(
        {
            "ATR": [1.0] * len(body_atr),
            "close": [100.0] * len(body_atr),
            "body_atr": body_atr,
        }
    )
    strategy.dp = SimpleNamespace(
        get_analyzed_dataframe=lambda _pair, _timeframe: (dataframe, None)
    )

    return strategy.custom_exit(
        pair="BTC/USDT:USDT",
        trade=SimpleNamespace(is_short=is_short),
        current_time=datetime.now(UTC),
        current_rate=100.0,
        current_profit=current_profit,
    )


@pytest.mark.parametrize(
    ("body_atr", "is_short", "expected"),
    [
        ([0.0, -2.01], False, "亏损大阴线反转平多"),
        ([0.0, 2.01], True, "亏损大阳线反转平空"),
    ],
)
def test_single_large_body_reversal_requires_loss(body_atr, is_short, expected) -> None:
    assert custom_exit(body_atr, is_short=is_short, current_profit=-0.01) == expected
    assert custom_exit(body_atr, is_short=is_short, current_profit=0.01) is None


@pytest.mark.parametrize(
    ("body_atr", "is_short", "expected"),
    [
        ([-1.20, -1.31], False, "连续两根大阴线反转平多"),
        ([1.20, 1.31], True, "连续两根大阳线反转平空"),
    ],
)
def test_two_large_body_reversals_exit_immediately(body_atr, is_short, expected) -> None:
    assert custom_exit(body_atr, is_short=is_short, current_profit=0.01) == expected


@pytest.mark.parametrize(
    ("body_atr", "is_short"),
    [
        ([-1.25, -1.25], False),
        ([1.25, 1.25], True),
        ([3.0, -0.1], True),
        ([-3.0, 0.1], False),
    ],
)
def test_two_large_body_reversals_require_same_direction_and_sum_over_threshold(
    body_atr, is_short
) -> None:
    assert custom_exit(body_atr, is_short=is_short, current_profit=0.01) is None
