"""CK Quant public research template.

Derived only from Freqtrade's public SampleStrategy:
https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/templates/sample_strategy.py

This is an educational baseline, not a profitable strategy claim. It contains no
private CK Quant strategy logic.
"""

from pandas import DataFrame
import talib.abstract as ta
from technical import qtpylib
from freqtrade.strategy import IStrategy, IntParameter


class CKQPublicTemplate(IStrategy):
    INTERFACE_VERSION = 3
    can_short = True
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count = 200

    minimal_roi = {"60": 0.01, "30": 0.02, "0": 0.04}
    stoploss = -0.10
    trailing_stop = False
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    buy_rsi = IntParameter(low=10, high=50, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=90, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(low=50, high=90, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(low=10, high=50, default=30, space="exit", optimize=True, load=True)

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe)
        dataframe["tema"] = ta.TEMA(dataframe, timeperiod=9)
        bands = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_middleband"] = bands["mid"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value)
            & (dataframe["tema"] <= dataframe["bb_middleband"])
            & (dataframe["tema"] > dataframe["tema"].shift(1))
            & (dataframe["volume"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "public_sample_long")
        dataframe.loc[
            qtpylib.crossed_above(dataframe["rsi"], self.short_rsi.value)
            & (dataframe["tema"] > dataframe["bb_middleband"])
            & (dataframe["tema"] < dataframe["tema"].shift(1))
            & (dataframe["volume"] > 0),
            ["enter_short", "enter_tag"],
        ] = (1, "public_sample_short")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value)
            & (dataframe["tema"] > dataframe["bb_middleband"])
            & (dataframe["tema"] < dataframe["tema"].shift(1))
            & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1
        dataframe.loc[
            qtpylib.crossed_above(dataframe["rsi"], self.exit_short_rsi.value)
            & (dataframe["tema"] <= dataframe["bb_middleband"])
            & (dataframe["tema"] > dataframe["tema"].shift(1))
            & (dataframe["volume"] > 0),
            "exit_short",
        ] = 1
        return dataframe
