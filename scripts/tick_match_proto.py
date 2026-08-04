#!/usr/bin/env python
"""
Tick 撮合验证原型 v2 —— 对照实验：同一交易，OHLCV 假设 vs 真实 tick 序列

核心问题：
  回测中"止损/止盈先触发哪个"用 15m bar 的 high/low 判断（假设路径未知）。
  真实 tick 序列能给出精确答案。本原型验证两者差异有多大。

方法：
  1. 从 tick 聚合 15m bars（得到 OHLCV 视角）
  2. 生成一批模拟入场（固定间隔入场，模拟常见策略行为）
  3. 每个入场：
     a) OHLCV 法：检查后续 bar 的 low/high 是否触及止损/止盈，取先触及者
     b) Tick 法：在真实 tick 序列上逐笔扫描，看先触发哪个、成交价多少
  4. 对比两种方法的 出场原因、出场价、盈亏

用法:
    python tick_match_proto.py <tick_feather> 
"""
import sys
import os

import numpy as np
import pandas as pd

# 参数（贴近 15m bar 内波动，制造"同一 bar 双触发"场景暴露 OHLCV 假设误差）
STOPLOSS = 0.005    # 0.5%
TAKE_PROFIT = 0.005  # 1:1


def load_ticks(path: str) -> pd.DataFrame:
    df = pd.read_feather(path)
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def build_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    ts = ticks["timestamp"].to_numpy()
    price = ticks["price"].to_numpy()
    bar_id = ts // 900_000  # 15m
    out = []
    for b in np.unique(bar_id):
        m = bar_id == b
        p = price[m]
        out.append((b, p[0], p.max(), p.min(), p[-1], m.sum()))
    bars = pd.DataFrame(out, columns=["bar_id", "open", "high", "low", "close", "n_ticks"])
    return bars


def simulate_entry_times(ticks: pd.DataFrame, interval_min: int = 240) -> list[tuple[int, float]]:
    """每 4 小时在 bar 收盘价入场一次（模拟持续交易的策略行为）"""
    bars = build_bars(ticks)
    entries = []
    for _, r in bars.iloc[::16].iterrows():  # 每 16 个 15m bar = 4h
        entries.append((int(r["bar_id"]), float(r["close"])))
    return entries


def match_ohlcv(bars: pd.DataFrame, entry_bar: int, entry_price: float):
    """OHLCV 假设法：用后续 bar 的 high/low 判断触发顺序"""
    sub = bars[bars["bar_id"] > entry_bar]
    for _, r in sub.iterrows():
        # long: 止损 low<=stop, 止盈 high>=tp —— 假设同 bar 内先触止损（保守）
        stop = entry_price * (1 - STOPLOSS)
        tp = entry_price * (1 + TAKE_PROFIT)
        hit_stop = r["low"] <= stop
        hit_tp = r["high"] >= tp
        if hit_stop and hit_tp:
            # 未知顺序：保守假设先止损
            return "stop_loss", stop, int(r["bar_id"])
        if hit_stop:
            return "stop_loss", stop, int(r["bar_id"])
        if hit_tp:
            return "take_profit", tp, int(r["bar_id"])
    return "open", None, None


def match_tick(ticks: pd.DataFrame, entry_ts: int, entry_price: float, max_ms: int = 900_000 * 300):
    """真实 tick 法：逐笔扫描，精确触发顺序（观察窗口与 OHLCV 法对齐）"""
    stop = entry_price * (1 - STOPLOSS)
    tp = entry_price * (1 + TAKE_PROFIT)
    ts = ticks["timestamp"].to_numpy()
    price = ticks["price"].to_numpy()
    start_idx = int(np.searchsorted(ts, entry_ts))
    for i in range(start_idx, len(ts)):
        if ts[i] - entry_ts > max_ms:
            break
        p = price[i]
        if p <= stop:
            return "stop_loss", stop, int(ts[i])
        if p >= tp:
            return "take_profit", tp, int(ts[i])
    return "open", None, None


def main():
    paths = sys.argv[1:] if len(sys.argv) > 1 else []
    if not paths:
        print("用法: python tick_match_proto.py <tick_feather...>")
        sys.exit(1)
    # 支持多文件：合并（注意内存 —— 验证阶段直接合并，集成版用流式）
    frames = [load_ticks(p) for p in paths]
    ticks = pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)
    del frames
    print(f"tick 总数: {len(ticks):,}  时间跨度: "
          f"{pd.Timestamp(ticks['timestamp'].min(), unit='ms', tz='UTC')} ~ "
          f"{pd.Timestamp(ticks['timestamp'].max(), unit='ms', tz='UTC')}")

    entries = simulate_entry_times(ticks)
    print(f"模拟入场: {len(entries)}")

    bars = build_bars(ticks)
    print(f"15m bars: {len(bars)}")

    results = []
    for bar_id, price in entries:
        ts_entry = bar_id * 900_000 + 1  # bar 开始后 1ms
        r_ohlcv = match_ohlcv(bars, bar_id, price)
        r_tick = match_tick(ticks, ts_entry, price)
        # 盈亏
        def pnl(exit_price, direction=1):
            if exit_price is None:
                return 0.0
            return (exit_price - price) / price

        results.append({
            "entry_price": price,
            "ohlcv_reason": r_ohlcv[0], "ohlcv_pnl": pnl(r_ohlcv[1]),
            "tick_reason": r_tick[0], "tick_pnl": pnl(r_tick[1]),
            "agree": r_ohlcv[0] == r_tick[0],
        })

    df = pd.DataFrame(results)
    n = len(df)
    agree = df["agree"].mean()
    print(f"\n=== 对照结果 ===")
    print(f"出场原因一致率: {agree:.1%}  ({df['agree'].sum()}/{n})")
    print(f"\nOHLCV 法:  止盈 {df[df.ohlcv_reason=='take_profit'].shape[0]}  止损 {df[df.ohlcv_reason=='stop_loss'].shape[0]}  未出场 {df[df.ohlcv_reason=='open'].shape[0]}")
    print(f"Tick 法:   止盈 {df[df.tick_reason=='take_profit'].shape[0]}  止损 {df[df.tick_reason=='stop_loss'].shape[0]}  未出场 {df[df.tick_reason=='open'].shape[0]}")
    print(f"\nOHLCV 总盈亏: {df['ohlcv_pnl'].sum():+.4f}")
    print(f"Tick  总盈亏: {df['tick_pnl'].sum():+.4f}")
    print(f"\n差异明细（前 15 笔）:")
    for _, r in df.head(15).iterrows():
        mark = "✅" if r["agree"] else "❌"
        print(f"  {mark} 入@{r['entry_price']:.1f}  OHLCV={r['ohlcv_reason']}({r['ohlcv_pnl']:+.3%})  "
              f"Tick={r['tick_reason']}({r['tick_pnl']:+.3%})")


if __name__ == "__main__":
    main()
