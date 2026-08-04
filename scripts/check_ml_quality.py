"""分析 v2 双标签模型预测质量"""
import glob, os
import numpy as np
import pandas as pd

pred_dir = r"D:\Eric Cheng\Documents\CK_Quant\user_data\models\ck-rs-freqai-v2\backtesting_predictions"
files = sorted(glob.glob(os.path.join(pred_dir, "*.feather")))
print(f"预测文件数: {len(files)}")

all_preds = []
for f in files:
    df = pd.read_feather(f)
    base = os.path.basename(f).replace("_prediction.feather", "")
    parts = base.split("_")
    pair = parts[1].upper() + "/USDT:USDT"
    df['pair'] = pair
    all_preds.append(df)

pred_df = pd.concat(all_preds, ignore_index=True)
pred_df['date'] = pd.to_datetime(pred_df['date'], utc=True)
print(f"总行数: {len(pred_df)}")
print("列:", list(pred_df.columns)[:12])

# 加载 K 线
kline_cache = {}
def get_close(pair):
    if pair in kline_cache:
        return kline_cache[pair]
    sym = pair.split('/')[0].lower()
    path = rf"D:\Eric Cheng\Documents\CK_Quant\user_data\data\binance\futures\{sym}_USDT_USDT-15m-futures.feather"
    df = pd.read_feather(path)
    df['date'] = pd.to_datetime(df['date'], utc=True)
    kline_cache[pair] = df
    return df

rows = []
for pair, grp in pred_df.groupby('pair'):
    kdf = get_close(pair)
    m = grp.merge(kdf[['date', 'close', 'high', 'low', 'open']], on='date', how='left')
    # 计算 ATR192
    import talib.abstract as ta
    m['ATR'] = ta.ATR(m, timeperiod=192)
    # 未来 16 根实际极值
    fwd_high = m['high'].shift(-16).rolling(16).max()
    fwd_low = m['low'].shift(-16).rolling(16).min()
    m['act_high_atr'] = (fwd_high - m['close']) / m['ATR']
    m['act_low_atr'] = (fwd_low - m['close']) / m['ATR']
    rows.append(m)

df = pd.concat(rows, ignore_index=True)

print("\n=== 模型预测质量（fwd_high_atr）===")
for col, act in [('&-fwd_high_atr', 'act_high_atr'), ('&-fwd_low_atr', 'act_low_atr')]:
    valid = df.dropna(subset=[col, act])
    valid = valid[np.isfinite(valid[col]) & np.isfinite(valid[act])]
    corr = valid[col].corr(valid[act])
    print(f"{col}: 相关={corr:.4f} 样本={len(valid)}")
    # 方向一致率（预测正/负 vs 实际正/负）
    agree = ((valid[col] > 0) == (valid[act] > 0)).mean()
    print(f"  正负一致率: {agree:.2%}")
    # 分层
    q = valid[col].quantile([0.2, 0.8])
    top = valid[valid[col] >= q[0.8]][act].mean()
    bot = valid[valid[col] <= q[0.2]][act].mean()
    print(f"  预测高20%实际值: {top:.4f}  预测低20%实际值: {bot:.4f}  差异: {top-bot:.4f}")
