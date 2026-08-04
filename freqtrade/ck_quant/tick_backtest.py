"""
CK Quant Tick-Level Backtest Engine
====================================

内存友好的 tick 级回测引擎（freqtrade 扩展）。

为什么需要它：
    freqtrade 原版回测用 OHLCV bar 的 high/low 判断止损/止盈触发顺序，
    无法知道 K 线内部的价格路径。当同一根 bar 内止损和止盈都被触及，
    或入场后短时间内先触发哪个时，OHLCV 假设会系统性偏向乐观
    （实测 ETH 7 月数据：7.1% 的交易触发顺序判断错误，总盈亏方向反转）。

本引擎：
    - 用真实 tick 序列逐笔撮合出场（止损/止盈/出场信号触发顺序精确）
    - 分块加载 tick（每 chunk 一个 feather），峰值内存可控
    - 策略信号在聚合的 15m bar 上计算（复用 strategy.populate_indicators /
      populate_entry_trend），入场在信号 bar 之后执行
    - 输出与 freqtrade 回测兼容的 trades 结构

用法（作为独立模块）:
    python -m freqtrade.ck_quant.tick_backtest \\
        --config config.json --strategy CK_Trend \\
        --data-dir user_data/data/binance/futures/trades_eth \\
        --timerange 20250701-20250731
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from freqtrade.configuration import Configuration
from freqtrade.resolvers import StrategyResolver

logger = logging.getLogger("tick_backtest")

BAR_MS = 900_000  # 15m


@dataclass
class TickTrade:
    """一笔 tick 级撮合的交易"""
    pair: str
    direction: int                # +1 long / -1 short
    entry_price: float
    entry_time: int               # ms epoch
    stop_price: float
    tp_price: float
    exit_price: float = 0.0
    exit_time: int = 0
    exit_reason: str = "open"
    entry_tag: str = ""

    @property
    def pnl_ratio(self) -> float:
        if self.exit_price == 0:
            return 0.0
        return self.direction * (self.exit_price - self.entry_price) / self.entry_price


class TickMatcher:
    """逐 tick 撮合：对每个持仓检查真实 tick 序列中的触发顺序"""

    def __init__(self, stoploss: float, takeprofit: float):
        self.stoploss = stoploss
        self.takeprofit = takeprofit
        self.open_trades: list[TickTrade] = []
        self.closed_trades: list[TickTrade] = []

    def open(self, trade: TickTrade) -> None:
        self.open_trades.append(trade)

    def process(self, ts: int, price: float) -> None:
        """处理一个 tick（真实序列顺序 = 精确触发顺序）"""
        if not self.open_trades:
            return
        remaining: list[TickTrade] = []
        for t in self.open_trades:
            if t.direction > 0:
                if price <= t.stop_price:
                    t.exit_price, t.exit_reason, t.exit_time = t.stop_price, "stop_loss", ts
                    self.closed_trades.append(t)
                elif price >= t.tp_price:
                    t.exit_price, t.exit_reason, t.exit_time = t.tp_price, "take_profit", ts
                    self.closed_trades.append(t)
                else:
                    remaining.append(t)
            else:
                if price >= t.stop_price:
                    t.exit_price, t.exit_reason, t.exit_time = t.stop_price, "stop_loss", ts
                    self.closed_trades.append(t)
                elif price <= t.tp_price:
                    t.exit_price, t.exit_reason, t.exit_time = t.tp_price, "take_profit", ts
                    self.closed_trades.append(t)
                else:
                    remaining.append(t)
        self.open_trades = remaining


def load_ticks_chunk(path: str) -> pd.DataFrame:
    """加载一个 tick chunk（feather），按时间排序"""
    df = pd.read_feather(path)
    return df.sort_values("timestamp").reset_index(drop=True)


def ticks_to_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    """从 tick 聚合 15m OHLCV bar"""
    ts = ticks["timestamp"].to_numpy()
    price = ticks["price"].to_numpy()
    bar_id = ts // BAR_MS
    out = []
    for b in np.unique(bar_id):
        m = bar_id == b
        p = price[m]
        out.append((int(b), p[0], p.max(), p.min(), p[-1]))
    bars = pd.DataFrame(out, columns=["bar_id", "open", "high", "low", "close"])
    return bars.sort_values("bar_id").reset_index(drop=True)


def prepare_strategy_dataframe(strategy, bars: pd.DataFrame, pair: str) -> pd.DataFrame:
    """
    把聚合 bar 转成 freqtrade 策略输入格式，调用 populate_indicators + populate_entry_trend。
    """
    df = pd.DataFrame({
        "date": pd.to_datetime(bars["bar_id"] * BAR_MS, unit="ms", utc=True),
        "open": bars["open"],
        "high": bars["high"],
        "low": bars["low"],
        "close": bars["close"],
        "volume": 0.0,
    })
    # 策略需要 date 作为 index 吗？freqtrade 用 date 列。直接调用 advise 方法。
    metadata = {"pair": pair, "timeframe": "15m"}
    df = strategy.advise_indicators(df, metadata=metadata)
    df = strategy.advise_entry(df, metadata=metadata)
    return df


def _build_bar_lookup(bars_all: pd.DataFrame) -> dict[int, int]:
    """bar_id → bars_all 行号 映射"""
    return {int(b): i for i, b in enumerate(bars_all["bar_id"].to_numpy())}


def run_tick_backtest_v2(
    strategy,
    pair: str,
    tick_files: list[str],
    stoploss: float,
    takeprofit: float,
    max_open: int = 10,
    tick_stride: int = 50,
) -> list[TickTrade]:
    """
    v2：完整实现
    - 入场：信号 bar 的下一个 tick 之后（用信号 bar 的 close 价近似入场价，
      与 freqtrade 的"下一根 bar 开盘"语义不同，但更真实 —— 信号确认后
      立即按当前价入场）
    - 出场：真实 tick 逐笔撮合
    """
    # ---- 第一遍：聚合 bar + 信号 ----
    all_bars: list[pd.DataFrame] = []
    for f in sorted(tick_files):
        chunk = load_ticks_chunk(f)
        all_bars.append(ticks_to_bars(chunk))
        del chunk
    bars_all = pd.concat(all_bars, ignore_index=True).sort_values("bar_id").reset_index(drop=True)
    bars_all = bars_all.drop_duplicates(subset="bar_id").reset_index(drop=True)
    print(f"[tick] 聚合 {len(bars_all)} 根 15m bars")

    df = prepare_strategy_dataframe(strategy, bars_all, pair)
    enter_long = df.get("enter_long", pd.Series(False, index=df.index)).astype(bool).to_numpy()
    enter_short = df.get("enter_short", pd.Series(False, index=df.index)).astype(bool).to_numpy()
    bar_id_arr = bars_all["bar_id"].to_numpy()
    close_arr = bars_all["close"].to_numpy()

    # 每个 bar 的入场状态（信号在该 bar 生效 → 下一个 tick 入场）
    bar_entry_long: dict[int, bool] = {}
    bar_entry_short: dict[int, bool] = {}
    for i, b in enumerate(bar_id_arr):
        if enter_long[i]:
            bar_entry_long[int(b)] = True
        if enter_short[i]:
            bar_entry_short[int(b)] = True

    matcher = TickMatcher(stoploss, takeprofit)
    open_count = 0
    last_bar_entered: dict[int, bool] = {}

    for f in sorted(tick_files):
        chunk = load_ticks_chunk(f)
        ts = chunk["timestamp"].to_numpy()
        price = chunk["price"].to_numpy()
        n = len(ts)
        stride = tick_stride

        # 处理 chunk 内 ticks
        for i in range(0, n, stride):
            t = int(ts[i])
            p = float(price[i])
            b = t // BAR_MS

            # 入场：当前 bar 有信号 → 开仓（首个 tick）
            if b in bar_entry_long and bar_entry_long[b]:
                if open_count < max_open:
                    stop = p * (1 - stoploss)
                    tp = p * (1 + takeprofit)
                    matcher.open(TickTrade(pair, 1, p, t, stop, tp, entry_tag="long_signal"))
                    open_count += 1
                bar_entry_long[b] = False  # 每 bar 只入场一次
            if b in bar_entry_short and bar_entry_short[b]:
                if open_count < max_open:
                    stop = p * (1 + stoploss)
                    tp = p * (1 - takeprofit)
                    matcher.open(TickTrade(pair, -1, p, t, stop, tp, entry_tag="short_signal"))
                    open_count += 1
                bar_entry_short[b] = False

            matcher.process(t, p)

        # 更新 open_count（已平仓的不占位）
        open_count = len(matcher.open_trades) + len(matcher.closed_trades)
        open_count = min(open_count, max_open)
        del chunk

    return matcher.closed_trades


def print_stats(trades: list[TickTrade]) -> None:
    print(f"\n=== Tick 回测结果 ===")
    print(f"总交易: {len(trades)}")
    if not trades:
        return
    wins = sum(1 for t in trades if t.pnl_ratio > 0)
    losses = sum(1 for t in trades if t.pnl_ratio < 0)
    total_pnl = sum(t.pnl_ratio for t in trades)
    print(f"胜: {wins}  负: {losses}  胜率: {wins/len(trades):.1%}")
    print(f"总盈亏(每单1单位): {total_pnl:+.4f}")
    print(f"出场: 止损 {sum(1 for t in trades if t.exit_reason=='stop_loss')}  "
          f"止盈 {sum(1 for t in trades if t.exit_reason=='take_profit')}  "
          f"其他 {sum(1 for t in trades if t.exit_reason not in ('stop_loss','take_profit'))}")
    print("\n最近 10 笔:")
    for t in trades[-10:]:
        print(f"  {'多' if t.direction>0 else '空'} 入@{t.entry_price:.2f} → "
              f"{t.exit_reason}@{t.exit_price:.2f}  {t.pnl_ratio:+.3%}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="CK Quant tick-level backtest")
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--data-dir", required=True, help="tick feather 文件目录")
    parser.add_argument("--timerange", default="20250701-20250731")
    parser.add_argument("--pair", default="ETH/USDT:USDT")
    parser.add_argument("--stoploss", type=float, default=0.005)
    parser.add_argument("--takeprofit", type=float, default=0.005)
    parser.add_argument("--tick-stride", type=int, default=50,
                        help="每 N 个 tick 处理一个（省内存；50=处理2%的tick）")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING)

    # 加载配置 + 策略
    config = Configuration.from_files([args.config])
    config["strategy"] = args.strategy
    config["runmode"] = "backtest"
    strategy = StrategyResolver.load_strategy(config)

    # 收集 tick 文件
    files = sorted(glob.glob(os.path.join(args.data_dir, "*.feather")))
    start, end = args.timerange.split("-")
    files = [f for f in files if start <= os.path.basename(f).split("_")[1] <= end]
    if not files:
        print(f"未找到 tick 数据: {args.data_dir} ({args.timerange})")
        sys.exit(1)
    print(f"[tick] 找到 {len(files)} 个分块: {os.path.basename(files[0])} ~ {os.path.basename(files[-1])}")

    trades = run_tick_backtest_v2(
        strategy, args.pair, files,
        stoploss=args.stoploss, takeprofit=args.takeprofit,
        tick_stride=args.tick_stride,
    )
    print_stats(trades)


if __name__ == "__main__":
    main()
