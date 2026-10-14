"""
dry-run 顶档盘口缓存（2026-10-14 P1）单元测试。

背景：dry-run 的止损穿越判定 _dry_is_price_crossed 只读 bids[0]/asks[0]，
而 check_dry_limit_order_filled 原先为此对每个止损单、每轮发一次 depth=20 的
fetch_l2_order_book（33 持仓实测 ≈3.0s/轮）。

改动：把主循环批量行情（_prefetch_exit_rates 的 get_tickers）里的买一/卖一存进
Exchange._dry_top_of_book，止损穿越判定优先复用；未命中/过期回退原逻辑。

本文件同时给出**反证**：不预热缓存时，原 L2 请求仍会发生（说明测试确实在测新能力）。
"""

from tests.conftest import get_patched_exchange


PAIR = "ETH/USDT:USDT"


def _stop_order(exchange, symbol: str, stop_price: float):
    return {
        "id": "dry_run_stoploss_test",
        "symbol": symbol,
        "status": "open",
        "type": "market",
        "ft_order_type": "stoploss",
        "side": "sell",
        "amount": 1.0,
        "filled": 0.0,
        "remaining": 1.0,
        "price": stop_price,
        exchange._ft_has["stop_price_prop"]: stop_price,
    }


def _enable_l2(mocker, exchange):
    """让 _dry_is_price_crossed / 止损分支认为交易所支持 L2 盘口（否则两者都会提前返回）。"""
    mocker.patch.object(exchange, "exchange_has", return_value=True)


def test_dry_top_of_book_hit_avoids_l2_request(mocker, default_conf):
    """命中缓存：止损穿越判定不得发 L2 请求。"""
    exchange = get_patched_exchange(mocker, default_conf)
    _enable_l2(mocker, exchange)
    assert exchange._config["dry_run"] is True
    exchange.set_dry_top_of_book({PAIR: {"bid": 100.0, "ask": 100.5}})

    l2 = mocker.patch.object(
        exchange, "fetch_l2_order_book", side_effect=AssertionError("命中缓存时不应发 L2 请求")
    )
    # 卖方向止损、止损价 97.0 < 卖一 100.5 ⇒ 未穿越
    out = exchange.check_dry_limit_order_filled(_stop_order(exchange, PAIR, 97.0))
    assert out["status"] == "open"
    assert l2.call_count == 0


def test_dry_top_of_book_crossed_fetches_real_depth(mocker, default_conf):
    """真穿越（罕见）：仍要补一次真实深度，保证成交价插值保真度不变。"""
    exchange = get_patched_exchange(mocker, default_conf)
    _enable_l2(mocker, exchange)
    assert exchange._config["dry_run"] is True
    exchange.set_dry_top_of_book({PAIR: {"bid": 100.0, "ask": 100.5}})

    deep = {"bids": [[100.0, 5.0], [99.9, 5.0]], "asks": [[100.5, 5.0], [100.6, 5.0]]}
    l2 = mocker.patch.object(exchange, "fetch_l2_order_book", return_value=deep)
    # 止损价 101.0 > 卖一 100.5 ⇒ 穿越
    out = exchange.check_dry_limit_order_filled(_stop_order(exchange, PAIR, 101.0))
    assert l2.call_count == 1
    assert out["status"] == "closed"
    assert out["filled"] == 1.0


def test_dry_top_of_book_miss_falls_back(mocker, default_conf):
    """未预热/未命中：必须回退到原有 L2 请求（反证：证明上面两个用例测的是新能力）。"""
    exchange = get_patched_exchange(mocker, default_conf)
    _enable_l2(mocker, exchange)
    assert exchange._config["dry_run"] is True
    exchange._dry_top_of_book = {}
    exchange._dry_top_of_book_ts = 0.0

    deep = {"bids": [[100.0, 5.0]], "asks": [[100.5, 5.0]]}
    l2 = mocker.patch.object(exchange, "fetch_l2_order_book", return_value=deep)
    out = exchange.check_dry_limit_order_filled(_stop_order(exchange, PAIR, 97.0))
    assert l2.call_count == 1          # 原逻辑照旧
    assert out["status"] == "open"


def test_dry_top_of_book_ttl_expires(mocker, default_conf):
    """TTL 过期后不得复用陈旧盘口。"""
    exchange = get_patched_exchange(mocker, default_conf)
    _enable_l2(mocker, exchange)
    assert exchange._config["dry_run"] is True
    exchange.set_dry_top_of_book({PAIR: {"bid": 100.0, "ask": 100.5}})
    exchange._dry_top_of_book_ts -= 10_000         # 人为过期（毫秒）
    assert exchange.dry_top_of_book(PAIR) is None


def test_set_dry_top_of_book_noop_live(mocker, default_conf):
    """非 dry-run 一律不缓存（实盘路径零影响）。"""
    exchange = get_patched_exchange(mocker, default_conf)
    exchange._config["dry_run"] = False
    exchange.set_dry_top_of_book({PAIR: {"bid": 100.0, "ask": 100.5}})
    assert exchange.dry_top_of_book(PAIR) is None
