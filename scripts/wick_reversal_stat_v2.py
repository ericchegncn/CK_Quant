#!/usr/bin/env python
"""
反转长上下影线 K 线形态统计 v2 —— 全对合并汇总

与 v1 的区别：
  1. 按形态 label 全对合并（不再 per-pair 堆叠），样本量足够才有统计意义
  2. 添加"反转方向"约束：锤子线（底部+长下影+阳实体）/ 射击之星（顶部+长上影+阴实体）
  3. 添加经典形态比例：影线 >= 2×实体（K线教科书锤子/流星定义）
  4. 区域阈值扫描：ZONE_ATR = 1.0 / 1.5 / 2.0（底部/顶部区域的宽松度）
  5. 输出未来 4/8/16 根上涨概率、平均收益、2.75ATR 涨跌幅达标的概率

统计目标（对应 CK_Trend 出场/反手逻辑）：
  - 平多信号候选：顶部射击之星（长上影+阴实体）→ 未来下跌概率
  - 平空信号候选：底部锤子线（长下影+阳实体）→ 未来上涨概率
  - 反手信号候选：同上（平仓同时反向开仓）
"""
import glob
import os

import numpy as np
import pandas as pd
import talib.abstract as ta

DATA_DIR = r"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures"
SLOW_PERIOD = 192          # 与 CK_Trend 一致
WICK_THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 3.5]   # 影线 ATR 阈值
BODY_MAX = 2.75            # 实体上限
ZONE_ATRS = [1.0, 1.5, 2.0]  # 底部/顶部区域 ATR 距离扫描
FWD_BARS = [4, 8, 16]      # 未来观察窗口
RESULT_BAR = 16            # 主要反转判定窗口


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    atr = ta.ATR(df, timeperiod=SLOW_PERIOD)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    open_ = df["open"].to_numpy()

    body = close - open_
    body_atr = body / atr
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    upper_wick_atr = upper_wick / atr
    lower_wick_atr = lower_wick / atr

    out = df.copy()
    out["atr"] = atr
    out["body_atr"] = body_atr
    out["upper_wick_atr"] = upper_wick_atr
    out["lower_wick_atr"] = lower_wick_atr

    # 192 周期极值（shift 避免未来函数）
    roll_high_prev = pd.Series(high).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).max().shift(1)
    roll_low_prev = pd.Series(low).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).min().shift(1)
    out["dist_high_atr"] = (roll_high_prev - close) / atr
    out["dist_low_atr"] = (close - roll_low_prev) / atr

    for n in FWD_BARS:
        out[f"fwd_high_{n}"] = pd.Series(high).shift(-n).rolling(n).max() / close - 1
        out[f"fwd_low_{n}"] = pd.Series(low).shift(-n).rolling(n).min() / close - 1
        out[f"fwd_ret_{n}"] = pd.Series(close).shift(-n) / close - 1

    out["fwd_gain_2p75"] = out["fwd_high_16"] * close / atr >= 2.75
    out["fwd_loss_2p75"] = out["fwd_low_16"] * close / atr <= -2.75
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
        for nb in FWD_BARS:
            d.setdefault(f"up_{nb}", 0.0)
            d.setdefault(f"ret_{nb}", 0.0)
            d[f"up_{nb}"] += (sub[f"fwd_ret_{nb}"] > 0).mean()
            d[f"ret_{nb}"] += sub[f"fwd_ret_{nb}"].mean()
        d.setdefault("gain_2p75", 0.0)
        d.setdefault("loss_2p75", 0.0)
        d["gain_2p75"] += sub["fwd_gain_2p75"].mean()
        d["loss_2p75"] += sub["fwd_loss_2p75"].mean()

    for fi, f in enumerate(files):
        df = pd.read_feather(f)
        if len(df) < 2000:
            continue
        out = compute_metrics(df)
        b = out["body_atr"]
        upw = out["upper_wick_atr"]
        lw = out["lower_wick_atr"]

        # 基准
        add("[基准] 全部", pd.Series(True, index=out.index), out)

        for za in ZONE_ATRS:
            bottom = out["dist_low_atr"] < za
            top = out["dist_high_atr"] < za
            add(f"[基准] 底部区域<{za}", bottom, out)
            add(f"[基准] 顶部区域<{za}", top, out)

            for wt in WICK_THRESHOLDS:
                # 形态1：底部锤子线（长下影 + 阳实体 + 实体不超上限）→ 看涨反转（平空/反手做多）
                cond = (
                    bottom
                    & (lw >= wt)
                    & (b > 0)
                    & (b < BODY_MAX)
                )
                add(f"锤子线 底部<{za}+下影≥{wt}+阳实体", cond, out)

                # 形态2：顶部射击之星（长上影 + 阴实体）→ 看跌反转（平多/反手做空）
                cond = (
                    top
                    & (upw >= wt)
                    & (b < 0)
                    & (b > -BODY_MAX)
                )
                add(f"射击之星 顶部<{za}+上影≥{wt}+阴实体", cond, out)

                # 形态3：底部倒锤（长上影 + 阳实体，底部区域的冲高回落）
                cond = (
                    bottom
                    & (upw >= wt)
                    & (b > 0)
                    & (b < BODY_MAX)
                )
                add(f"倒锤 底部<{za}+上影≥{wt}+阳实体", cond, out)

                # 形态4：顶部吊颈（长下影 + 阴实体，顶部区域的下探回升）
                cond = (
                    top
                    & (lw >= wt)
                    & (b < 0)
                    & (b > -BODY_MAX)
                )
                add(f"吊颈 顶部<{za}+下影≥{wt}+阴实体", cond, out)

                # 形态5：底部+长下影（不限实体方向，v1 口径，带 zone 前缀避免重复累加）
                cond = bottom & (lw >= wt) & (b.abs() < BODY_MAX)
                add(f"底部<{za}+下影≥{wt}+实体<{BODY_MAX}", cond, out)

                # 形态6：顶部+长上影（不限实体方向，v1 口径，带 zone 前缀避免重复累加）
                cond = top & (upw >= wt) & (b.abs() < BODY_MAX)
                add(f"顶部<{za}+上影≥{wt}+实体<{BODY_MAX}", cond, out)

        # 经典比例形态：影线 >= 2×|实体|（不限区域，样本更多）
        for k in [2.0, 3.0]:
            cond = (lw >= k * b.abs()) & (b > 0)
            add(f"经典锤子 下影≥{k}×实体+阳", cond, out)
            cond = (upw >= k * b.abs()) & (b < 0)
            add(f"经典流星 上影≥{k}×实体+阴", cond, out)

        if (fi + 1) % 20 == 0:
            print(f"  已处理 {fi+1}/{len(files)}", flush=True)

    # ---- 输出 ---- 
    rows = []
    for label, d in agg.items():
        if d["cnt"] == 0:
            continue
        r = {"形态": label, "总样本": d["n"], "覆盖对": d["cnt"]}
        for nb in FWD_BARS:
            r[f"涨概率_{nb}根%"] = d[f"up_{nb}"] / d["cnt"] * 100
            r[f"均收益_{nb}根%"] = d[f"ret_{nb}"] / d["cnt"] * 100
        r["16根涨2.75ATR%"] = d["gain_2p75"] / d["cnt"] * 100
        r["16根跌2.75ATR%"] = d["loss_2p75"] / d["cnt"] * 100
        rows.append(r)

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 300)
    pd.set_option("display.max_rows", 300)
    show_cols = ["形态", "总样本", "覆盖对",
                 "涨概率_4根%", "涨概率_8根%", "涨概率_16根%",
                 "均收益_16根%", "16根涨2.75ATR%", "16根跌2.75ATR%"]
    print("\n" + "=" * 130)
    print("反转长上下影线 K 线形态统计（114 对合并）")
    print("=" * 130)
    print(res[show_cols].to_string(index=False))
    out_csv = r"D:\Eric Cheng\Documents\CK_Quant\user_data\wick_reversal_v2_results.csv"
    res.to_csv(out_csv, index=False)
    print(f"\n已保存: {out_csv}")


if __name__ == "__main__":
    main()
