#!/usr/bin/env python
"""
CK_Trend 出场信号阈值统计 —— 单根/双根/三根反转 + 长影线

目标：用 114 对长历史数据，统计出最优的出场反转阈值。
出场信号有效性定义：信号出现后，价格"不再朝原持仓方向走"（反转成立）。

对多头持仓（平多信号 = 阴线/下跌组合）：
  反转成立 = 未来 N 根内最高价不超过 入场价 + 2.75×ATR（不再创新高）
  或 未来 N 根收益 < 0（价格下跌）
对空头持仓（平空信号 = 阳线/上涨组合）：镜像。

统计对象（与 CK_Trend 出场逻辑对应）：
  A. 单根：body_atr < -X（平多）/ > +X（平空），X 扫描
  B. 双根：连续两根同向，实体和 < -X / > +X，X 扫描
  C. 三根：连续三根同向，实体和 < -X / > +X，X 扫描
  D. 长影线（底部/顶部区域）
"""
import glob
import os

import numpy as np
import pandas as pd
import talib.abstract as ta

DATA_DIR = r"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures"
SLOW_PERIOD = 192
ZONE_ATR = 1.0
# 未来观察窗口（根 15m K 线）—— 匹配策略平均持仓 28.7h ≈ 115 根
# 16根=4h  48根=12h  96根=1天  120根≈平均持仓  192根=2天
FWD_LIST = [16, 48, 96, 120, 192]
FWD_MAIN = 120       # 主判定窗口（≈平均持仓）
REV_ATR = 2.75  # 反转判定幅度

# 阈值扫描范围
SINGLE_X = [1.5, 1.8, 2.0, 2.3, 2.5, 2.75, 3.0, 3.5, 4.0]
DOUBLE_X = [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
TRIPLE_X = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]
WICK_X = [1.5, 2.0, 2.5, 2.75, 3.0]


def compute(df: pd.DataFrame) -> pd.DataFrame:
    atr = ta.ATR(df, timeperiod=SLOW_PERIOD)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    open_ = df["open"].to_numpy()

    out = df.copy()
    out["atr"] = atr
    out["body_atr"] = (close - open_) / atr
    out["upper_wick_atr"] = (high - np.maximum(open_, close)) / atr
    out["lower_wick_atr"] = (np.minimum(open_, close) - low) / atr

    out["roll_high_prev"] = pd.Series(high).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).max().shift(1)
    out["roll_low_prev"] = pd.Series(low).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).min().shift(1)
    out["dist_high_atr"] = (out["roll_high_prev"] - close) / atr
    out["dist_low_atr"] = (close - out["roll_low_prev"]) / atr

    # 未来窗口（多窗口：匹配不同持仓周期）
    for n in FWD_LIST:
        fwd_high = pd.Series(high).shift(-n).rolling(n).max()
        fwd_low = pd.Series(low).shift(-n).rolling(n).min()
        fwd_close = pd.Series(close).shift(-n)
        out[f"fwd_high_atr_{n}"] = (fwd_high - close) / atr
        out[f"fwd_low_atr_{n}"] = (fwd_low - close) / atr
        out[f"fwd_ret_{n}"] = fwd_close / close - 1
        out[f"fwd_no_new_high_{n}"] = out[f"fwd_high_atr_{n}"] < REV_ATR
        out[f"fwd_no_new_low_{n}"] = out[f"fwd_low_atr_{n}"] > -REV_ATR
        out[f"fwd_down_{n}"] = out[f"fwd_ret_{n}"] < 0
        out[f"fwd_up_{n}"] = out[f"fwd_ret_{n}"] > 0
    return out


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*15m-futures.feather")))
    print(f"发现 {len(files)} 个交易对")

    # 聚合器：label -> {n, no_new_high, no_new_low, down, up, avg_ret}
    agg: dict[str, dict] = {}

    def add(label: str, cond: pd.Series, out: pd.DataFrame):
        n = int(cond.sum())
        if n < 50:
            return
        sub = out[cond]
        d = agg.setdefault(label, {"n": 0, "cnt": 0})
        d["n"] += n
        d["cnt"] += 1
        for w in FWD_LIST:
            d.setdefault(f"nh_{w}", 0.0)
            d.setdefault(f"nl_{w}", 0.0)
            d.setdefault(f"down_{w}", 0.0)
            d.setdefault(f"up_{w}", 0.0)
            d.setdefault(f"ret_{w}", 0.0)
            d[f"nh_{w}"] += sub[f"fwd_no_new_high_{w}"].mean()
            d[f"nl_{w}"] += sub[f"fwd_no_new_low_{w}"].mean()
            d[f"down_{w}"] += sub[f"fwd_down_{w}"].mean()
            d[f"up_{w}"] += sub[f"fwd_up_{w}"].mean()
            d[f"ret_{w}"] += sub[f"fwd_ret_{w}"].mean()

    for fi, f in enumerate(files):
        df = pd.read_feather(f)
        if len(df) < 3000:
            continue
        out = compute(df)
        body = out["body_atr"]
        wick_low = out["lower_wick_atr"]
        wick_up = out["upper_wick_atr"]
        bottom = out["dist_low_atr"] < ZONE_ATR
        top = out["dist_high_atr"] < ZONE_ATR

        # 基准
        add("[基准] 全部", pd.Series(True, index=out.index), out)
        add("[基准] 底部区域", bottom, out)
        add("[基准] 顶部区域", top, out)

        # A. 单根反转（平多 = 大阴线；平空 = 大阳线）
        for x in SINGLE_X:
            add(f"A单根 平多 阴线<{-x}", body < -x, out)
            add(f"A单根 平空 阳线>{x}", body > x, out)

        # B. 双根反转
        sum2 = body + body.shift(1)
        for x in DOUBLE_X:
            add(f"B双根 平多 和<{-x}", sum2 < -x, out)
            add(f"B双根 平空 和>{x}", sum2 > x, out)

        # C. 三根反转
        sum3 = body + body.shift(1) + body.shift(2)
        for x in TRIPLE_X:
            add(f"C三根 平多 和<{-x}", sum3 < -x, out)
            add(f"C三根 平空 和>{x}", sum3 > x, out)

        # D. 长影线（底部区域超长下影线 → 看涨反转；顶部区域超长上影线 → 看跌反转）
        for x in WICK_X:
            add(f"D影线 底部+下影≥{x}", bottom & (wick_low >= x), out)
            add(f"D影线 顶部+上影≥{x}", top & (wick_up >= x), out)

        if (fi + 1) % 25 == 0:
            print(f"  已处理 {fi+1}/{len(files)}", flush=True)

    # 输出
    rows = []
    for label, d in agg.items():
        if d["cnt"] == 0:
            continue
        r = {
            "形态": label,
            "总样本": d["n"],
            "每对": round(d["n"] / d["cnt"], 1),
        }
        for w in FWD_LIST:
            r[f"不创新高_{w}根%"] = d[f"nh_{w}"] / d["cnt"] * 100
            r[f"不创新低_{w}根%"] = d[f"nl_{w}"] / d["cnt"] * 100
            r[f"未来涨_{w}根%"] = d[f"up_{w}"] / d["cnt"] * 100
            r[f"均收益_{w}根%"] = d[f"ret_{w}"] / d["cnt"] * 100
        rows.append(r)
    res = pd.DataFrame(rows)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_rows", 200)
    print("\n" + "=" * 160)
    print("CK_Trend 出场信号阈值统计（114 对合并；120根≈平均持仓 28.7h）")
    print("=" * 160)
    # 主窗口列优先展示
    main_cols = ["形态", "总样本", "每对",
                 f"不创新高_{FWD_MAIN}根%", f"不创新低_{FWD_MAIN}根%",
                 f"未来涨_{FWD_MAIN}根%", f"均收益_{FWD_MAIN}根%",
                 f"均收益_48根%", f"均收益_96根%", f"均收益_192根%"]
    print(res[main_cols].to_string(index=False))
    res.to_csv(r"D:\Eric Cheng\Documents\CK_Quant\user_data\exit_threshold_stats.csv", index=False)
    print("\n已保存: user_data/exit_threshold_stats.csv")


if __name__ == "__main__":
    main()
