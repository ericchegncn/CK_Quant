#!/usr/bin/env python
"""从 binance.vision 下载 trades，每 7 天落盘一个独立文件（避免大文件合并 OOM）。
用法: python download_vision_chunked.py <SYMBOL> <start> <end> <out_dir>
输出: <out_dir>/<SYMBOL>_<YYYYMMDD>_<YYYYMMDD>.feather  （每段一个文件）
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
CHUNK_DAYS = 7


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
                    print(f"    下载失败 {day}", flush=True)
                    return None
                time.sleep(2)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(workdir)
        df = pd.read_csv(csv_path, dtype={"id": "int64", "time": "int64"},
                         usecols=["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"])
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

    cur = start_d
    while cur <= end_d:
        seg_end = min(cur + dt.timedelta(days=CHUNK_DAYS - 1), end_d)
        frames = []
        d = cur
        while d <= seg_end:
            df = download_day(symbol, d.strftime("%Y-%m-%d"), tempfile.gettempdir())
            if df is not None and len(df) > 0:
                frames.append(df)
            d += dt.timedelta(days=1)
        if frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = merged.drop_duplicates(subset="id").sort_values("timestamp").reset_index(drop=True)
            out_path = os.path.join(out_dir, f"{symbol}_{cur.strftime('%Y%m%d')}_{seg_end.strftime('%Y%m%d')}.feather")
            merged.to_feather(out_path)
            print(f"✅ {os.path.basename(out_path)}: {len(merged)} 条", flush=True)
            del merged, frames
            import gc; gc.collect()
        cur = seg_end + dt.timedelta(days=1)

    print("===== 全部完成 =====", flush=True)


if __name__ == "__main__":
    main()
