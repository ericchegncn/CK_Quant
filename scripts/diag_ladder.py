"""检查交易明细：挂单价是否真的是历史结构位"""
import zipfile, json, glob, os
import numpy as np
import pandas as pd

results_dir = r"D:\Eric Cheng\Documents\CK_Quant\user_data\backtest_results"
zips = sorted(glob.glob(os.path.join(results_dir, "*.zip")), key=os.path.getmtime, reverse=True)
z = zips[0]
print("最新:", os.path.basename(z))

with zipfile.ZipFile(z) as zf:
    inner = [n for n in zf.namelist() if n.endswith(".json") and "config" not in n and "_market" not in n and "_wallet" not in n]
    data = json.load(zf.open(inner[0]))

strat = data["strategy"]["CK_RS_FreqAI"]
trades = strat.get("trades", [])

print(f"\n=== 全部 {len(trades)} 笔交易 ===")
for t in trades:
    print(f"  {t.get('pair','?'):<15} {'空' if t.get('is_short') else '多'} "
          f"开:{t.get('open_rate',0):>10.2f} 收:{t.get('close_rate',0):>10.2f} "
          f"利润%:{t.get('profit_ratio',0)*100:>7.2f} 持仓:{t.get('trade_duration','?')}m "
          f"→ {t.get('exit_reason','?')}")

print("\n=== 出场原因 ===")
for r in strat.get("exit_reason_summary", []):
    print(f"  {r.get('key','?'):<30} 次数:{r.get('trades',0):>5} 利润%:{r.get('profit_total_pct',0):>9.2f} 胜:{r.get('wins',0)} 负:{r.get('losses',0)}")
