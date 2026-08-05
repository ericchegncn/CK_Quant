#!/usr/bin/env python
"""
长影线反转形态统计 —— 为 CK_Trend 出场逻辑改进提供数据依据

统计目标：
  1. 底部区域出现超长下影线（实体不足 2.75 ATR）→ 未来上涨概率 vs 基准
  2. 底部区域"前一根长下影线下跌 + 当前小实体阳线"→ 未来上涨概率 vs 基准
  3. 顶部区域镜像（超长上影线）→ 未来下跌概率

区域定义（用户指定）：
  底部区间：close 距 192 周期最低价的 ATR 距离 < 阈值
  顶部区间：close 距 192 周期最高价的 ATR 距离 < 阈值

输出：各形态 vs 基准的 未来N根上涨概率 / 平均涨幅 / 样本数
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import talib.abstract as ta

DATA_DIR = r"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures"
SLOW_PERIOD = 192          # 与 CK_Trend 一致
WICK_THRESHOLDS = [2.0, 2.5, 2.75, 3.0, 3.5]   # 影线 ATR 阈值（扫描多个）
BODY_MAX = 2.75            # 实体上限（"实体不足 2.75 ATR"）
ZONE_ATR = 1.0             # 底部/顶部区域：距极值 < 1 ATR
FWD_BARS = [4, 8, 16]      # 未来观察窗口（根）
RESULT_BAR = 16            # 主要反转判定窗口（4小时）


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有指标（向量化）"""
    atr = ta.ATR(df, timeperiod=SLOW_PERIOD)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    open_ = df["open"].to_numpy()

    # 实体与影线（ATR 归一化）
    body = close - open_
    body_atr = body / atr
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    upper_wick_atr = upper_wick / atr
    lower_wick_atr = lower_wick / atr

    # 192 周期极值（shift(1) 避免包含当前 K 线 = 无未来函数）
    df["roll_high_prev"] = pd.Series(high).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).max().shift(1)
    df["roll_low_prev"] = pd.Series(low).rolling(SLOW_PERIOD, min_periods=SLOW_PERIOD).min().shift(1)

    out = df.copy()
    out["atr"] = atr
    out["body_atr"] = body_atr
    out["upper_wick_atr"] = upper_wick_atr
    out["lower_wick_atr"] = lower_wick_atr

    # 距 192 周期极值的 ATR 距离
    out["dist_high_atr"] = (out["roll_high_prev"] - close) / atr
    out["dist_low_atr"] = (close - out["roll_low_prev"]) / atr

    # 未来窗口：最高价 / 最低价 / 收盘（shift 前瞻仅用于统计，不用于策略）
    for n in FWD_BARS:
        out[f"fwd_high_{n}"] = pd.Series(high).shift(-n).rolling(n).max() / close - 1
        out[f"fwd_low_{n}"] = pd.Series(low).shift(-n).rolling(n).min() / close - 1
        out[f"fwd_ret_{n}"] = pd.Series(close).shift(-n) / close - 1

    # 未来 16 根内是否达到 +2.75 ATR 涨幅（反转强度）
    out["fwd_gain_2p75"] = out["fwd_high_16"] * close / atr >= 2.75
    out["fwd_loss_2p75"] = out["fwd_low_16"] * close / atr <= -2.75
    return out


def summarize(cond: pd.Series, out: pd.DataFrame, label: str, results: dict):
    """统计一个条件的未来表现 vs 基准"""
    n = int(cond.sum())
    if n < 30:
        return  # 样本太少无意义
    sub = out[cond]
    entry = {
        "label": label,
        "n": n,
    }
    for nb in FWD_BARS:
        entry[f"up_prob_{nb}"] = (sub[f"fwd_ret_{nb}"] > 0).mean()
        entry[f"avg_ret_{nb}"] = sub[f"fwd_ret_{nb}"].mean()
    entry["gain_2p75_prob"] = sub["fwd_gain_2p75"].mean()
    entry["loss_2p75_prob"] = sub["fwd_loss_2p75"].mean()
    results.append(entry)


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*15m-futures.feather")))
    print(f"发现 {len(files)} 个交易对")
    results: list[dict] = []

    for fi, f in enumerate(files):
        pair = os.path.basename(f).split("-")[0]
        df = pd.read_feather(f)
        if len(df) < 2000:
            continue
        out = compute_metrics(df)

        # ---- 区域判定 ----
        bottom_zone = out["dist_low_atr"] < ZONE_ATR        # 底部区域
        top_zone = out["dist_high_atr"] < ZONE_ATR          # 顶部区域

        # 基准 1：全部时刻
        summarize(pd.Series(True, index=out.index), out, f"[基准] 全部", results)
        # 基准 2：底部区域
        summarize(bottom_zone, out, f"[基准] 底部区域", results)
        # 基准 3：顶部区域
        summarize(top_zone, out, f"[基准] 顶部区域", results)

        # ---- 形态 A：底部 + 单根超长下影线（实体不足）----
        for wt in WICK_THRESHOLDS:
            cond = (
                bottom_zone
                & (out["lower_wick_atr"] >= wt)
                & (out["body_atr"].abs() < BODY_MAX)
            )
            summarize(cond, out, f"形态A 底部+下影线≥{wt}+实体<{BODY_MAX}", results)

        # ---- 形态 B：底部 + 前一根长下影线下跌 + 当前小实体阳线 ----
        prev_lower_wick = out["lower_wick_atr"].shift(1)
        prev_body_atr = out["body_atr"].shift(1)
        for wt in WICK_THRESHOLDS:
            cond = (
                bottom_zone
                & (prev_lower_wick >= wt)
                & (prev_body_atr < 0)                      # 前一根是下跌 K 线
                & (out["body_atr"] > 0)                    # 当前是阳线
                & (out["body_atr"] < BODY_MAX)             # 实体不足 2.75
            )
            summarize(cond, out, f"形态B 底部+前影线≥{wt}+小阳线", results)

        # ---- 形态 C：顶部 + 单根超长上影线（实体不足）----
        for wt in WICK_THRESHOLDS:
            cond = (
                top_zone
                & (out["upper_wick_atr"] >= wt)
                & (out["body_atr"].abs() < BODY_MAX)
            )
            summarize(cond, out, f"形态C 顶部+上影线≥{wt}+实体<{BODY_MAX}", results)

        # ---- 形态 D：顶部 + 前一根长上影线阳线 + 当前小实体阴线 ----
        prev_upper_wick = out["upper_wick_atr"].shift(1)
        for wt in WICK_THRESHOLDS:
            cond = (
                top_zone
                & (prev_upper_wick >= wt)
                & (prev_body_atr > 0)                      # 前一根是上涨 K 线
                & (out["body_atr"] < 0)                    # 当前是阴线
                & (out["body_atr"].abs() < BODY_MAX)
            )
            summarize(cond, out, f"形态D 顶部+前影线≥{wt}+小阴线", results)

        if (fi + 1) % 20 == 0:
            print(f"  已处理 {fi+1}/{len(files)}", flush=True)

    # ---- 输出汇总 ----
    res = pd.DataFrame(results)
    if res.empty:
        print("无有效样本")
        return

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    pd.set_option("display.max_rows", 200)

    print("\n" + "=" * 120)
    print("长影线反转形态统计（全对汇总）")
    print("=" * 120)
    show_cols = ["label", "n", "up_prob_4", "up_prob_8", "up_prob_16",
                 "avg_ret_16", "gain_2p75_prob"]
    print(res[show_cols].to_string(index=False))

    # 保存
    out_csv = r"D:\Eric Cheng\Documents\CK_Quant\user_data\wick_stat_results.csv"
    res.to_csv(out_csv, index=False)
    print(f"\n已保存: {out_csv}")


if __name__ == "__main__":
    main()
