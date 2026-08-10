#!/usr/bin/env python
"""
反转平仓信号统一定参统计 v3 —— 大阴阳线 + 1~2根超长上下影线，窗口 96/192 对比

目标：用 114 对大样本，为 CK_Trend 反转平仓参数定最优值：
  1. 大阴阳线（单/双/三根，每根同向）—— 参数对比基准
  2. 单根超长影线：顶部+上影≥X ATR（平多候选）/ 底部+下影≥X ATR（平空候选）
  3. 两根影线组合：前一根超长影线 + 当前确认 K 线
  4. 极值窗口 SLOW 96 与 192 都统计（区域定义用 dist_high/low 相对 96/192 极值）

判定口径（与 exit_threshold_stat.py 一致，方便横向对比）：
  平多候选（顶部形态/大阴线）→ 理想：未来不创新高、未来涨概率低、均收益低
  平空候选（底部形态/大阳线）→ 理想：未来涨概率高、均收益高（做多方向）
  主窗口 FWD_MAIN=120 根（≈平均持仓 28.7h），辅窗口 48/192
"""
import glob
import os

import numpy as np
import pandas as pd
import talib.abstract as ta

DATA_DIR = r"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures"
SLOW_PERIODS = [96, 192]            # 极值窗口（对比）
ZONE_ATRS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]   # 区域 ATR 距离扫描
WICK_X = [1.0, 1.5, 2.0, 2.5, 3.0]  # 影线 ATR 阈值
BODY_MAX = 2.75                     # 实体上限（"小实体"）
FWD_LIST = [48, 120, 192]
FWD_MAIN = 120
REV_ATR = 2.75

# 大阴阳线阈值（与策略/现有统计一致）
SINGLE_X = [1.8, 2.0, 2.3, 2.5, 2.75, 3.0]
DOUBLE_X = [2.5, 3.0, 3.5, 4.0, 4.5]
TRIPLE_X = [3.5, 4.0, 4.5, 5.0, 5.5, 6.0]


def compute(df: pd.DataFrame, slow: int) -> pd.DataFrame:
    atr = ta.ATR(df, timeperiod=slow)
    close = df["close"].to_numpy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    open_ = df["open"].to_numpy()

    out = df.copy()
    out["atr"] = atr
    out["body_atr"] = (close - open_) / atr
    out["upper_wick_atr"] = (high - np.maximum(open_, close)) / atr
    out["lower_wick_atr"] = (np.minimum(open_, close) - low) / atr

    rh = pd.Series(high).rolling(slow, min_periods=slow).max().shift(1)
    rl = pd.Series(low).rolling(slow, min_periods=slow).min().shift(1)
    out["dist_high_atr"] = (rh - close) / atr
    out["dist_low_atr"] = (close - rl) / atr

    for n in FWD_LIST:
        fh = pd.Series(high).shift(-n).rolling(n).max()
        fl = pd.Series(low).shift(-n).rolling(n).min()
        fc = pd.Series(close).shift(-n)
        out[f"fwd_high_atr_{n}"] = (fh - close) / atr
        out[f"fwd_low_atr_{n}"] = (fl - close) / atr
        out[f"fwd_ret_{n}"] = fc / close - 1
        out[f"nh_{n}"] = out[f"fwd_high_atr_{n}"] < REV_ATR   # 不创新高
        out[f"nl_{n}"] = out[f"fwd_low_atr_{n}"] > -REV_ATR   # 不创新低
        out[f"up_{n}"] = out[f"fwd_ret_{n}"] > 0
    return out


def main():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*15m-futures.feather")))
    print(f"发现 {len(files)} 个交易对")
    agg: dict[str, dict] = {}

    def add(label: str, cond: pd.Series, out: pd.DataFrame):
        n = int(cond.sum())
        if n < 100:
            return
        sub = out[cond]
        d = agg.setdefault(label, {"n": 0, "cnt": 0})
        d["n"] += n
        d["cnt"] += 1
        for w in FWD_LIST:
            for k in ("nh", "nl", "up", "ret"):
                d.setdefault(f"{k}_{w}", 0.0)
            d[f"nh_{w}"] += sub[f"nh_{w}"].mean()
            d[f"nl_{w}"] += sub[f"nl_{w}"].mean()
            d[f"up_{w}"] += sub[f"up_{w}"].mean()
            d[f"ret_{w}"] += sub[f"fwd_ret_{w}"].mean()

    for fi, f in enumerate(files):
        df = pd.read_feather(f)
        if len(df) < 3000:
            continue
        for slow in SLOW_PERIODS:
            out = compute(df, slow)
            b = out["body_atr"]
            upw = out["upper_wick_atr"]
            lw = out["lower_wick_atr"]
            tag = f"W{slow}"

            # ---- 基准 ----
            add(f"[{tag}基准] 全部", pd.Series(True, index=out.index), out)

            # ---- 大阴阳线（每根同向）----
            for x in SINGLE_X:
                add(f"[{tag}]单阴<-{x}", b < -x, out)
                add(f"[{tag}]单阳>{x}", b > x, out)
            sum2 = b + b.shift(1)
            for x in DOUBLE_X:
                add(f"[{tag}]双阴和<-{x}", (b < 0) & (b.shift(1) < 0) & (sum2 < -x), out)
                add(f"[{tag}]双阳和>{x}", (b > 0) & (b.shift(1) > 0) & (sum2 > x), out)
            sum3 = b + b.shift(1) + b.shift(2)
            for x in TRIPLE_X:
                add(f"[{tag}]三阴和<-{x}",
                    (b < 0) & (b.shift(1) < 0) & (b.shift(2) < 0) & (sum3 < -x), out)
                add(f"[{tag}]三阳和>{x}",
                    (b > 0) & (b.shift(1) > 0) & (b.shift(2) > 0) & (sum3 > x), out)

            # ---- 影线形态（区域 × 影线阈值）----
            for za in ZONE_ATRS:
                bottom = out["dist_low_atr"] < za
                top = out["dist_high_atr"] < za
                add(f"[{tag}底区<{za}基准]", bottom, out)
                add(f"[{tag}顶区<{za}基准]", top, out)
                for wx in WICK_X:
                    # 单根：底部+长下影 → 平空/反手做多候选
                    add(f"[{tag}]底<{za}+下影≥{wx}+实体<{BODY_MAX}",
                        bottom & (lw >= wx) & (b.abs() < BODY_MAX), out)
                    # 单根：顶部+长上影 → 平多候选
                    add(f"[{tag}]顶<{za}+上影≥{wx}+实体<{BODY_MAX}",
                        top & (upw >= wx) & (b.abs() < BODY_MAX), out)
                    # 两根：前一根长下影 + 当前阳线（底部确认反转）
                    add(f"[{tag}]底<{za}+前下影≥{wx}+当前阳",
                        bottom & (lw.shift(1) >= wx) & (b > 0) & (b < BODY_MAX), out)
                    # 两根：前一根长上影 + 当前阴线（顶部确认反转）
                    add(f"[{tag}]顶<{za}+前上影≥{wx}+当前阴",
                        top & (upw.shift(1) >= wx) & (b < 0) & (b > -BODY_MAX), out)

        if (fi + 1) % 25 == 0:
            print(f"  已处理 {fi+1}/{len(files)}", flush=True)

    # ---- 输出 ----
    rows = []
    for label, d in agg.items():
        if d["cnt"] == 0:
            continue
        r = {"形态": label, "总样本": d["n"], "每对": round(d["n"] / d["cnt"], 1)}
        for w in FWD_LIST:
            r[f"不创新高_{w}%"] = d[f"nh_{w}"] / d["cnt"] * 100
            r[f"不创新低_{w}%"] = d[f"nl_{w}"] / d["cnt"] * 100
            r[f"未来涨_{w}%"] = d[f"up_{w}"] / d["cnt"] * 100
            r[f"均收益_{w}%"] = d[f"ret_{w}"] / d["cnt"] * 100
        rows.append(r)

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 320)
    pd.set_option("display.max_rows", 400)
    out_csv = r"D:\Eric Cheng\Documents\CK_Quant\user_data\exit_signal_stat_v3.csv"
    res.to_csv(out_csv, index=False)

    # 打印：平空候选（底部/大阳线，看未来涨%与均收益）+ 平多候选（顶部/大阴线）
    main_cols = ["形态", "总样本", "每对",
                 f"不创新高_{FWD_MAIN}%", f"未来涨_{FWD_MAIN}%", f"均收益_{FWD_MAIN}%",
                 f"未来涨_48%", f"均收益_48%", f"均收益_192%"]
    print("\n" + "=" * 170)
    print(f"反转平仓信号统计（114对；主窗口 {FWD_MAIN}根≈28.7h；W96/W192 极值窗口对比）")
    print("=" * 170)
    print(res[main_cols].to_string(index=False))
    print(f"\n已保存: {out_csv}")


if __name__ == "__main__":
    main()
