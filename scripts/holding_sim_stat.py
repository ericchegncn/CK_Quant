#!/usr/bin/env python
"""
持仓模拟统计 —— 反转平仓参数定参（与策略口径一致）

之前统计的问题是"任意时刻出现形态 → 未来涨跌"，但策略是持仓中才触发反转平仓。
本脚本模拟 CK_Trend 的持仓状态（EMA12 方向 + 入场逻辑），
只统计【持仓中】出现反转信号时的未来表现，使统计口径与策略一致。

模拟逻辑（与 CK_Trend 一致）：
  - 入场：EMA12 向上(斜率>0) → 持多；EMA12 向下 → 持空（入场不猜方向）
  - 持仓状态 = 最近一次入场信号之后（无止损/出场模拟，纯状态标记）
  - 统计对象：持仓中，出现大阴阳线/影线反转信号的那根 K 线
  - 未来表现：信号后 N 根（对应持仓周期）的走势

输出：各信号档位 vs 持仓基准的 未来N根涨跌概率 / 均收益 / 样本数
"""
import glob
import os

import numpy as np
import pandas as pd
import talib.abstract as ta

DATA_DIR = r"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures"
SLOW_PERIOD = 192
ATR_VOL_MIN = 0.003          # 与策略入场 ATR_Volatility > 0.003 一致
MAX_BODY_ATR = 5.0           # 与策略 recent_max_body_atr_abs <= 5.0 一致
BODY_LOOKBACK = 6
FWD_LIST = [16, 48, 120]     # 4h / 12h / 30h（平均持仓 28.7h ≈ 120 根）
FWD_MAIN = 120

# 大阴阳线阈值扫描（与策略现状对照）
SINGLE_X = [1.8, 2.0, 2.3, 2.5, 2.75, 3.0]
DOUBLE_X = [2.5, 3.0, 3.5, 4.0, 4.5]
TRIPLE_X = [3.5, 4.0, 4.5, 5.0, 5.5, 6.0]

# 影线阈值
WICK_X = [1.0, 1.5, 2.0, 2.5]
ZONE_ATR = 2.5              # 区域（统计最优）


def simulate_holding(df: pd.DataFrame) -> pd.DataFrame:
    """模拟 EMA12 持仓状态：1=持多, -1=持空, 0=空仓"""
    ema12 = ta.EMA(df, timeperiod=12)
    ema_slope = ema12 - ema12.shift(1)          # 斜率（与策略一致）
    atr = ta.ATR(df, timeperiod=SLOW_PERIOD)

    atr_vol = atr / df['close']
    recent_max_body = (
        ((df['close'] - df['open']).abs() / atr)
        .rolling(BODY_LOOKBACK, min_periods=1).max()
    )

    long_entry = (ema_slope > 0) & (atr_vol > ATR_VOL_MIN) & (recent_max_body <= MAX_BODY_ATR)
    short_entry = (ema_slope < 0) & (atr_vol > ATR_VOL_MIN) & (recent_max_body <= MAX_BODY_ATR)

    # 状态机：入场信号后保持持仓，直到反向入场信号
    state = np.zeros(len(df), dtype=int)
    cur = 0
    le = long_entry.to_numpy()
    se = short_entry.to_numpy()
    for i in range(len(df)):
        if le[i]:
            cur = 1
        elif se[i]:
            cur = -1
        state[i] = cur
    df['holding'] = state
    return df


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    atr = ta.ATR(df, timeperiod=SLOW_PERIOD)
    close = df['close'].to_numpy()
    high = df['high'].to_numpy()
    low = df['low'].to_numpy()
    open_ = df['open'].to_numpy()

    out = df.copy()
    out['atr'] = atr
    out['body_atr'] = (close - open_) / atr
    out['upper_wick_atr'] = (high - np.maximum(open_, close)) / atr
    out['lower_wick_atr'] = (np.minimum(open_, close) - low) / atr

    rh = pd.Series(high).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).max().shift(1)
    rl = pd.Series(low).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).min().shift(1)
    out['dist_high_atr'] = (rh - close) / atr
    out['dist_low_atr'] = (close - rl) / atr

    for n in FWD_LIST:
        out[f'fwd_ret_{n}'] = pd.Series(close).shift(-n) / close - 1
        out[f'fwd_high_{n}'] = pd.Series(high).shift(-n).rolling(n).max() / close - 1
        out[f'fwd_low_{n}'] = pd.Series(low).shift(-n).rolling(n).min() / close - 1
    return out


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*15m-futures.feather")))
    print(f"发现 {len(files)} 个交易对")
    agg: dict[str, dict] = {}

    def add(label: str, cond: pd.Series, out: pd.DataFrame):
        n = int(cond.sum())
        if n < 30:
            return
        sub = out[cond]
        d = agg.setdefault(label, {"n": 0, "cnt": 0})
        d["n"] += n
        d["cnt"] += 1
        for w in FWD_LIST:
            d.setdefault(f"ret_{w}", 0.0)
            d.setdefault(f"up_{w}", 0.0)
            d.setdefault(f"maxfavor_{w}", 0.0)
            d[f"ret_{w}"] += sub[f"fwd_ret_{w}"].mean()
            d[f"up_{w}"] += (sub[f"fwd_ret_{w}"] > 0).mean()
            # 持仓方向下的最大有利偏移（持多看未来最高，持空看未来最低）
            is_long = sub['holding'] == 1
            favor = np.where(is_long, sub[f"fwd_high_{w}"], -sub[f"fwd_low_{w}"])
            d[f"maxfavor_{w}"] += favor.mean()

    for fi, f in enumerate(files):
        df = pd.read_feather(f)
        if len(df) < 3000:
            continue
        out = compute_metrics(df)
        out = simulate_holding(out)
        b = out['body_atr']
        upw = out['upper_wick_atr']
        lw = out['lower_wick_atr']
        hold_long = out['holding'] == 1
        hold_short = out['holding'] == -1

        # ---- 持仓基准 ----
        add("[基准] 持仓中(全部)", pd.Series(True, index=out.index), out)
        add("[基准] 持多中", hold_long, out)
        add("[基准] 持空中", hold_short, out)

        # ---- 大阴阳线（持仓中触发，方向匹配：持多遇阴线 / 持空遇阳线）----
        for x in SINGLE_X:
            add(f"单阴<-{x} 持多中", hold_long & (b < -x), out)
            add(f"单阳>{x} 持空中", hold_short & (b > x), out)
        sum2 = b + b.shift(1)
        for x in DOUBLE_X:
            add(f"双阴和<-{x} 持多中",
                hold_long & (b < 0) & (b.shift(1) < 0) & (sum2 < -x), out)
            add(f"双阳和>{x} 持空中",
                hold_short & (b > 0) & (b.shift(1) > 0) & (sum2 > x), out)
        sum3 = b + b.shift(1) + b.shift(2)
        for x in TRIPLE_X:
            add(f"三阴和<-{x} 持多中",
                hold_long & (b < 0) & (b.shift(1) < 0) & (b.shift(2) < 0) & (sum3 < -x), out)
            add(f"三阳和>{x} 持空中",
                hold_short & (b > 0) & (b.shift(1) > 0) & (b.shift(2) > 0) & (sum3 > x), out)

        # ---- 影线（持仓中触发）----
        bottom = out['dist_low_atr'] < ZONE_ATR
        top = out['dist_high_atr'] < ZONE_ATR
        for wx in WICK_X:
            add(f"顶+上影≥{wx} 持多中", hold_long & top & (upw >= wx), out)
            add(f"底+下影≥{wx} 持空中", hold_short & bottom & (lw >= wx), out)

        if (fi + 1) % 25 == 0:
            print(f"  已处理 {fi+1}/{len(files)}", flush=True)

    # ---- 输出 ----
    rows = []
    for label, d in agg.items():
        if d["cnt"] == 0:
            continue
        r = {"信号": label, "样本": d["n"], "每对": round(d["n"] / d["cnt"], 1)}
        for w in FWD_LIST:
            r[f"涨概率_{w}根%"] = d[f"up_{w}"] / d["cnt"] * 100
            r[f"均收益_{w}根%"] = d[f"ret_{w}"] / d["cnt"] * 100
            r[f"有利偏移_{w}根%"] = d[f"maxfavor_{w}"] / d["cnt"] * 100
        rows.append(r)

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 320)
    pd.set_option("display.max_rows", 400)
    out_csv = r"D:\Eric Cheng\Documents\CK_Quant\user_data\holding_sim_stats.csv"
    res.to_csv(out_csv, index=False)

    main_cols = ["信号", "样本", "每对",
                 f"涨概率_{FWD_MAIN}根%", f"均收益_{FWD_MAIN}根%", f"有利偏移_{FWD_MAIN}根%",
                 f"均收益_48根%", f"均收益_16根%"]
    print("\n" + "=" * 150)
    print("持仓模拟统计（持多中触发平多信号 → 未来收益；持空中触发平空信号 → 未来收益）")
    print(f"主窗口 {FWD_MAIN}根≈28.7h；有利偏移 = 持仓方向最大可获利幅度")
    print("=" * 150)
    print(res[main_cols].to_string(index=False))
    print(f"\n已保存: {out_csv}")


if __name__ == "__main__":
    main()
