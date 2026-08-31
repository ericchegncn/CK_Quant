"""
GainersLosersPairList - 涨跌幅双向排名 PairList

提供基于涨跌幅的双向动态交易对列表：
- number_assets: N → 涨幅前 N 个 + 跌幅前 N 个 = 共 2N 个交易对
- direction: both（默认，涨幅+跌幅都选）/ gainers（只选涨幅）/ losers（只选跌幅）
- lookback_days / lookback_period + lookback_timeframe: 基于历史K线的涨跌幅（可选）

支持与 VolumePairList / StaticPairList 混合使用（freqtrade 多 pairlist 串联，
各自结果并集汇总）。
"""

import logging
from datetime import timedelta
from typing import TypedDict

from pandas import DataFrame

from freqtrade.constants import ListPairsWithTimeframes, PairWithTimeframe
from freqtrade.exceptions import OperationalException
from freqtrade.exchange import timeframe_to_minutes, timeframe_to_prev_date
from freqtrade.exchange.exchange_types import Ticker, Tickers
from freqtrade.plugins.pairlist.IPairList import IPairList, PairlistParameter, SupportsBacktesting
from freqtrade.util import FtTTLCache, dt_now, format_ms_time


logger = logging.getLogger(__name__)


class SymbolWithPercentage(TypedDict):
    symbol: str
    percentage: float | None


class GainersLosersPairList(IPairList):
    is_pairlist_generator = True
    supports_backtesting = SupportsBacktesting.NO

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._stake_currency = self._config["stake_currency"]
        # 涨跌幅数量：gainers_count / losers_count 独立设置；兼容 number_assets（双向同数）
        self._gainers_count = self._pairlistconfig.get("gainers_count", None)
        self._losers_count = self._pairlistconfig.get("losers_count", None)
        if "number_assets" in self._pairlistconfig:
            self._gainers_count = self._pairlistconfig["number_assets"]
            self._losers_count = self._pairlistconfig["number_assets"]
        if self._gainers_count is None and self._losers_count is None:
            raise OperationalException(
                "`number_assets` (or `gainers_count` / `losers_count`) not specified. "
                'Please check your configuration for "pairlist.config.number_assets"'
            )
        self._direction = self._pairlistconfig.get("direction", "both")
        if self._direction not in ("both", "gainers", "losers"):
            raise OperationalException(
                "`direction` must be one of: both, gainers, losers. "
                f"Got: {self._direction}"
            )
        # 模式：filter = 原生过滤链（只在上家输出里排）；union = 混合并集（全市场独立选+合并）
        self._mode = self._pairlistconfig.get("mode", "filter")
        if self._mode not in ("filter", "union"):
            raise OperationalException(
                "`mode` must be one of: filter, union. "
                f"Got: {self._mode}"
            )
        self._min_value = self._pairlistconfig.get("min_value", None)
        self._max_value = self._pairlistconfig.get("max_value", None)
        self._refresh_period = self._pairlistconfig.get("refresh_period", 1800)
        self._pair_cache: FtTTLCache = FtTTLCache(maxsize=1, ttl=self._refresh_period)
        self._lookback_days = self._pairlistconfig.get("lookback_days", 0)
        self._lookback_timeframe = self._pairlistconfig.get("lookback_timeframe", "1d")
        self._lookback_period = self._pairlistconfig.get("lookback_period", 0)
        self._def_candletype = self._config["candle_type_def"]

        if (self._lookback_days > 0) and (self._lookback_period > 0):
            raise OperationalException(
                "Ambiguous configuration: lookback_days and lookback_period both set in pairlist "
                "config. Please set lookback_days only or lookback_period and lookback_timeframe "
                "and restart the bot."
            )

        if self._lookback_days > 0:
            self._lookback_timeframe = "1d"
            self._lookback_period = self._lookback_days

        self._tf_in_min = timeframe_to_minutes(self._lookback_timeframe)
        _tf_in_sec = self._tf_in_min * 60
        self._use_range = (self._tf_in_min > 0) and (self._lookback_period > 0)

        if self._use_range and (self._refresh_period < _tf_in_sec):
            raise OperationalException(
                f"Refresh period of {self._refresh_period} seconds is smaller than one "
                f"timeframe of {self._lookback_timeframe}. Please adjust refresh_period "
                f"to at least {_tf_in_sec} and restart the bot."
            )

        if not self._use_range and not (
            self._exchange.exchange_has("fetchTickers")
            and self._exchange.get_option("tickers_have_percentage")
        ):
            raise OperationalException(
                f"Exchange {self._exchange.name} does not support dynamic whitelist in this "
                "configuration. Please edit your config and either remove GainersLosersPairList, "
                "or switch to using candles and restart the bot."
            )

        candle_limit = self._exchange.ohlcv_candle_limit(
            self._lookback_timeframe, self._def_candletype
        )
        if self._lookback_period > candle_limit:
            raise OperationalException(
                "ChangeFilter requires lookback_period to not "
                f"exceed exchange max request size ({candle_limit})"
            )

    @property
    def needstickers(self) -> bool:
        return not self._use_range

    def short_desc(self) -> str:
        return (
            f"{self.name} - top {self._gainers_count} gainers + top {self._losers_count} "
            f"losers ({self._direction}) by percent change."
        )

    @staticmethod
    def description() -> str:
        return "Provides dynamic pair list based on percent change (gainers + losers)."

    @staticmethod
    def available_parameters() -> dict[str, PairlistParameter]:
        return {
            **IPairList.refresh_period_parameter(),
            "number_assets": {
                "type": "number",
                "default": 10,
                "description": "Number of pairs to select per direction",
                "help": "Select top N gainers and top N losers (2N pairs total when both). "
                "Alternatively use gainers_count / losers_count for asymmetric counts.",
            },
            "gainers_count": {
                "type": "number",
                "default": None,
                "description": "Number of top gainers to select",
                "help": "Select top N gainers. Overrides number_assets for gainers.",
            },
            "losers_count": {
                "type": "number",
                "default": None,
                "description": "Number of top losers to select",
                "help": "Select top N losers. Overrides number_assets for losers.",
            },
            "direction": {
                "type": "option",
                "default": "both",
                "options": ["both", "gainers", "losers"],
                "description": "Direction to select",
                "help": "both: top N gainers + top N losers. gainers: only top N gainers. "
                "losers: only top N losers.",
            },
            "mode": {
                "type": "option",
                "default": "filter",
                "options": ["filter", "union"],
                "description": "Filter-chain or union (hybrid) mode",
                "help": "filter: native freqtrade chain - rank within upstream pairlist only. "
                "union: select from whole market independently and merge with upstream "
                "(Volume + Gainers + Static can coexist).",
            },
            "min_value": {
                "type": "number",
                "default": None,
                "description": "Minimum percent change to include",
                "help": "Minimum value to use for filtering the pairlist.",
            },
            "max_value": {
                "type": "number",
                "default": None,
                "description": "Maximum percent change to include",
                "help": "Maximum value to use for filtering the pairlist.",
            },
            "lookback_days": {
                "type": "number",
                "default": 0,
                "description": "Lookback Days",
                "help": "Number of days to look back at.",
            },
            "lookback_timeframe": {
                "type": "string",
                "default": "1d",
                "description": "Lookback Timeframe",
                "help": "Timeframe to use for lookback.",
            },
            "lookback_period": {
                "type": "number",
                "default": 0,
                "description": "Lookback Period",
                "help": "Number of periods to look back at.",
            },
        }

    def gen_pairlist(self, tickers: Tickers) -> list[str]:
        pairlist = self._pair_cache.get("pairlist")
        if pairlist:
            return pairlist.copy()

        _pairlist = [
            k
            for k in self._exchange.get_markets(
                quote_currencies=[self._stake_currency], tradable_only=True, active_only=True
            ).keys()
        ]
        _pairlist = self.verify_blacklist(_pairlist, logger.info)

        if not self._use_range:
            filtered_tickers = [
                v
                for k, v in tickers.items()
                if (
                    self._exchange.get_pair_quote_currency(k) == self._stake_currency
                    and v["symbol"] in _pairlist
                )
            ]
            pairlist = [s["symbol"] for s in filtered_tickers]
        else:
            pairlist = _pairlist

        # As the first pairlist handler, the full market is only the ranking
        # universe.  It must not be treated as an upstream list for union mode.
        pairlist = self.filter_pairlist(pairlist, tickers, merge_with_upstream=False)
        self._pair_cache["pairlist"] = pairlist.copy()

        return pairlist

    def filter_pairlist(
        self,
        pairlist: list[str],
        tickers: dict,
        *,
        merge_with_upstream: bool = True,
    ) -> list[str]:
        # filter 模式：原生过滤链 —— 只在上家输出的候选里排涨跌幅
        # union 模式：混合并集 —— 从全市场独立选涨跌幅榜，并与上家结果合并
        if self._mode == "union":
            _pairlist = [
                k
                for k in self._exchange.get_markets(
                    quote_currencies=[self._stake_currency], tradable_only=True, active_only=True
                ).keys()
            ]
            _pairlist = self.verify_blacklist(_pairlist, logger.info)
        else:
            _pairlist = pairlist

        filtered_tickers: list[SymbolWithPercentage] = [
            {"symbol": k, "percentage": None} for k in _pairlist
        ]

        if self._use_range:
            filtered_tickers = self.fetch_percent_change_from_lookback_period(filtered_tickers)
        else:
            filtered_tickers = self.fetch_percent_change_from_tickers(filtered_tickers, tickers)

        if self._min_value is not None:
            filtered_tickers = [v for v in filtered_tickers if v["percentage"] > self._min_value]
        if self._max_value is not None:
            filtered_tickers = [v for v in filtered_tickers if v["percentage"] < self._max_value]

        # 分离涨幅榜和跌幅榜
        gainers = [v for v in filtered_tickers if (v["percentage"] or 0) >= 0]
        losers = [v for v in filtered_tickers if (v["percentage"] or 0) < 0]

        gainers_sorted = sorted(gainers, key=lambda t: t["percentage"] or 0, reverse=True)
        losers_sorted = sorted(losers, key=lambda t: t["percentage"] or 0, reverse=False)

        selected: list[str] = []
        if self._direction in ("both", "gainers") and self._gainers_count:
            selected += [s["symbol"] for s in gainers_sorted[: self._gainers_count]]
        if self._direction in ("both", "losers") and self._losers_count:
            selected += [s["symbol"] for s in losers_sorted[: self._losers_count]]

        pairs = self._whitelist_for_active_markets(selected)
        pairs = self.verify_blacklist(pairs, logmethod=logger.info)

        if self._mode == "union" and merge_with_upstream:
            # 混合并集：上家结果 + 涨跌幅榜（去重）
            return list(dict.fromkeys(list(pairlist) + pairs))
        return pairs

    def fetch_candles_for_lookback_period(
        self, filtered_tickers: list[SymbolWithPercentage]
    ) -> dict[PairWithTimeframe, DataFrame]:
        since_ms = (
            int(
                timeframe_to_prev_date(
                    self._lookback_timeframe,
                    dt_now()
                    + timedelta(
                        minutes=-(self._lookback_period * self._tf_in_min) - self._tf_in_min
                    ),
                ).timestamp()
            )
            * 1000
        )
        to_ms = (
            int(
                timeframe_to_prev_date(
                    self._lookback_timeframe, dt_now() - timedelta(minutes=self._tf_in_min)
                ).timestamp()
            )
            * 1000
        )
        self.log_once(
            f"Using change range of {self._lookback_period} candles, timeframe: "
            f"{self._lookback_timeframe}, starting from {format_ms_time(since_ms)} "
            f"till {format_ms_time(to_ms)}",
            logger.info,
        )
        needed_pairs: ListPairsWithTimeframes = [
            (p, self._lookback_timeframe, self._def_candletype)
            for p in [s["symbol"] for s in filtered_tickers]
            if p not in self._pair_cache
        ]
        candles = self._exchange.refresh_ohlcv_with_cache(needed_pairs, since_ms)
        return candles

    def fetch_percent_change_from_lookback_period(
        self, filtered_tickers: list[SymbolWithPercentage]
    ) -> list[SymbolWithPercentage]:
        candles = self.fetch_candles_for_lookback_period(filtered_tickers)

        for i, p in enumerate(filtered_tickers):
            pair_candles = (
                candles[(p["symbol"], self._lookback_timeframe, self._def_candletype)]
                if (p["symbol"], self._lookback_timeframe, self._def_candletype) in candles
                else None
            )

            if pair_candles is not None and not pair_candles.empty:
                current_close = pair_candles["close"].iloc[-1]
                previous_close = pair_candles["close"].shift(self._lookback_period).iloc[-1]
                pct_change = (
                    ((current_close - previous_close) / previous_close) * 100
                    if previous_close > 0
                    else 0
                )
                filtered_tickers[i]["percentage"] = pct_change
            else:
                filtered_tickers[i]["percentage"] = 0
        return filtered_tickers

    def fetch_percent_change_from_tickers(
        self, filtered_tickers: list[SymbolWithPercentage], tickers
    ) -> list[SymbolWithPercentage]:
        valid_tickers: list[SymbolWithPercentage] = []
        for p in filtered_tickers:
            if self._validate_pair(
                p["symbol"], tickers[p["symbol"]] if p["symbol"] in tickers else None
            ):
                p["percentage"] = tickers[p["symbol"]]["percentage"]
                valid_tickers.append(p)
        return valid_tickers

    def _validate_pair(self, pair: str, ticker: Ticker | None) -> bool:
        if ticker is None:
            return False
        # 排除无涨跌幅数据的交易对
        if ticker.get("percentage") is None:
            return False
        return True
