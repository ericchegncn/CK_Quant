"""计算含未实现盈亏的总回撤 vs 已平仓回撤（验证用户判断）"""
import zipfile, json, glob, os
import pandas as pd
import numpy as np

results_dir = r"D:\Eric Cheng\Documents\CK_Quant\user_data\backtest_results"
zips = sorted(glob.glob(os.path.join(results_dir, "*.zip")), key=os.path.getmtime, reverse=True)
z = zips[0]
print("最新结果:", os.path.basename(z))

with zipfile.ZipFile(z) as zf:
    inner = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "_market" not in n and "_wallet" not in n]
    data = json.load(zf.open(inner[0]))

# 找 Body3 策略
for name, strat in data["strategy"].items():
    if "Body3" in name:
        print(f"\n策略: {name}")
        trades = strat["trades"]
        print(f"交易数: {len(trades)}")
        # 回测配置信息
        if "backtest_details" in data:
            pass

        # 重建权益曲线（含未实现盈亏）
        # 每笔交易: open_date, close_date, profit_abs, open_rate, close_rate, is_short
        rows = []
        for t in trades:
            open_dt = pd.Timestamp(t["open_date"])
            close_dt = pd.Timestamp(t["close_date"])
            rows.append({
                "open_dt": open_dt, "close_dt": close_dt,
                "profit_abs": t.get("profit_abs", 0),
                "open_rate": t.get("open_rate", 0),
                "close_rate": t.get("close_rate", 0),
                "is_short": t.get("is_short", False),
                "amount": t.get("amount", 0),
                "leverage": t.get("leverage", 1),
            })
        tdf = pd.DataFrame(rows)

        # 起点资金（从结果中的起始余额推断）
        start_balance = 10000  # 常见默认，仅用于比例对比
        # 用每日余额变化重建
        # 已平仓收益曲线
        tdf = tdf.sort_values("close_dt")
        tdf["cum_profit"] = tdf["profit_abs"].cumsum()
        realized_balance = start_balance + tdf["cum_profit"]
        realized_dd = realized_balance.cummax() - realized_balance
        print(f"\n=== 已平仓视角（freqtrade 默认） ===")
        print(f"最大回撤: {realized_dd.max():.2f} USDT ({realized_dd.max()/realized_balance.cummax().max():.2%})")

        # 含未实现盈亏的视角：在每笔交易持仓期间，用当前价估算浮盈
        # 简化：用 open→close 的线性插值模拟持仓期价格，或者直接用 close_rate 对比 open_rate 估算
        # 更准确：回测有 _wallet 文件，但这里用交易级近似
        # 生成每分钟采样（粗粒度：每笔持仓期间的浮盈 = profit_abs * (持仓时间内的进度)）
        # 简化方案：浮盈在持仓期内线性增长（从0到profit_abs）
        print(f"\n=== 含未实现盈亏视角（线性近似） ===")
        # 收集所有时间点
        all_times = sorted(set(tdf["open_dt"]) | set(tdf["close_dt"]))
        # 用更细的采样：每 15 分钟
        full_range = pd.date_range(tdf["open_dt"].min(), tdf["close_dt"].max(), freq="15min")
        equity_unreal = np.full(len(full_range), start_balance, dtype=float)
        realized_series = np.zeros(len(full_range))
        # 逐笔累加：持仓期间贡献浮盈，平仓后贡献已实现
        for _, t in tdf.iterrows():
            mask = (full_range >= t["open_dt"]) & (full_range <= t["close_dt"])
            # 持仓期间: 从 0 线性到 profit_abs
            n = mask.sum()
            if n > 0:
                progress = np.linspace(0, 1, n)
                equity_unreal[mask] += t["profit_abs"] * progress
        # 已实现部分单独加（平仓后全额）
        for _, t in tdf.iterrows():
            mask = full_range > t["close_dt"]
            equity_unreal[mask] += t["profit_abs"]

        dd_unreal = np.maximum.accumulate(equity_unreal) - equity_unreal
        peak = np.maximum.accumulate(equity_unreal).max()
        print(f"最大回撤: {dd_unreal.max():.2f} USDT ({dd_unreal.max()/peak:.2%})")
        print(f"最终权益: {equity_unreal[-1]:.2f} USDT")

        print(f"\n=== 结论 ===")
        print(f"已平仓回撤比: {realized_dd.max()/peak:.2%}")
        print(f"含浮盈回撤比: {dd_unreal.max()/peak:.2%}")
        break
