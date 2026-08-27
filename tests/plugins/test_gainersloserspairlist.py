from unittest.mock import MagicMock

from freqtrade.plugins.pairlist.GainersLosersPairList import GainersLosersPairList
from freqtrade.util import FtTTLCache


def _pairlist() -> tuple[GainersLosersPairList, list[str], dict]:
    handler = object.__new__(GainersLosersPairList)
    handler._mode = "union"
    handler._stake_currency = "USDT"
    handler._use_range = False
    handler._min_value = None
    handler._max_value = None
    handler._direction = "both"
    handler._gainers_count = 10
    handler._losers_count = 5
    handler._pair_cache = FtTTLCache(maxsize=1, ttl=60)

    pairs = [f"P{i:02d}/USDT:USDT" for i in range(1, 41)]
    handler._exchange = MagicMock()
    handler._exchange.get_markets.return_value = {pair: {} for pair in pairs}
    handler._exchange.get_pair_quote_currency.return_value = "USDT"
    handler._whitelist_for_active_markets = lambda selected: selected
    handler.verify_blacklist = lambda selected, logmethod: selected

    percentages = {pair: float(index - 20) for index, pair in enumerate(pairs, 1)}
    tickers = {
        pair: {"symbol": pair, "percentage": percentage}
        for pair, percentage in percentages.items()
    }
    return handler, pairs, tickers


def test_union_generator_does_not_return_full_market() -> None:
    handler, pairs, tickers = _pairlist()

    result = handler.gen_pairlist(tickers)

    assert result == [*reversed(pairs[30:40]), *pairs[:5]]
    assert len(result) == 15


def test_union_filter_merges_with_upstream_pairlist() -> None:
    handler, pairs, tickers = _pairlist()
    upstream = pairs[10:30]

    result = handler.filter_pairlist(upstream, tickers)

    selected = [*reversed(pairs[30:40]), *pairs[:5]]
    assert result == list(dict.fromkeys([*upstream, *selected]))
