#!/usr/bin/env python
"""从 binance.vision 下载 trades，写入独立周文件（不合并到主文件，避免大文件 OOM）。
用法: python download_vision_weekly.py <SYMBOL> <start> <end> <out_dir>
输出: <out_dir>/<SYMBOL>_<start>_<end>.feather
"""
import sys
import os
import zipfile
import tempfile
import datetime as dt
import urllib.request
import time

import pandas as pd
import numpy as np

BASE_URL = "https://data.binance.vision/data/futures/um/daily/trades"


def download_day(symbol: str, day: str, workdir: str) -> pd.DataFrame | None:
    url = f"{BASE_URL}/{symbol}/{symbol}-trades-{day}.zip"
    zip_path = os.path.join(workdir, f"{symbol}-trades-{day}.zip")
    csv_path = os.path.join(workdir, f"{symbol}-trades-{day}.csv")
    try:
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, zip_path)
                break
            except Exception:
                if attempt == 2:
                    return None
                time.sleep(2)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(workdir)
        df = pd.read_csv(csv_path, dtype={"id": "int64", "time": "int64"},
                         usecols=["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"])
        # is_buyer_maker: True=卖方主动(sell), False=买方主动(buy)
        buyer_maker = df["is_buyer_maker"].to_numpy()
        side_arr = np.where(buyer_maker, "sell", "buy")
        return pd.DataFrame({
            "timestamp": df["time"].to_numpy(),
            "id": df["id"].astype(str).to_numpy(),
            "type": None,
            "side": side_arr,
            "price": df["price"].to_numpy(),
            "amount": df["qty"].to_numpy(),
            "cost": df["quote_qty"].to_numpy(),
        })[["timestamp", "id", "type", "side", "price", "amount", "cost"]]
    except Exception as e:
        print(f"    失败 {day}: {e}", flush=True)
        return None
    finally:
        for p in (zip_path, csv_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


def main():
    symbol = sys.argv[1]
    start = sys.argv[2]
    end = sys.argv[3]
    out_dir = sys.argv[4]
    os.makedirs(out_dir, exist_ok=True)

    start_d = dt.datetime.strptime(start, "%Y%m%d").date()
    end_d = dt.datetime.strptime(end, "%Y%m%d").date()

    frames = []
    cur = start_d
    while cur <= end_d:
        day_str = cur.strftime("%Y-%m-%d")
        df = download_day(symbol, day_str, tempfile.gettempdir())
        if df is not None and len(df) > 0:
            frames.append(df)
        cur += dt.timedelta(days=1)
        if len(frames) and len(frames) % 5 == 0:
            print(f"  累计 {sum(len(f) for f in frames)} 条 (至 {day_str})", flush=True)

    if not frames:
        print("无数据", flush=True)
        return
    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset="id").sort_values("timestamp").reset_index(drop=True)
    out_path = os.path.join(out_dir, f"{symbol}_{start}_{end}.feather")
    merged.to_feather(out_path)
    print(f"✅ {out_path}: {len(merged)} 条", flush=True)


if __name__ == "__main__":
    main()
