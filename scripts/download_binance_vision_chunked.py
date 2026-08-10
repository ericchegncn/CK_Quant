#!/usr/bin/env python
"""从 data.binance.vision 批量下载期货 trades 日文件，分块增量写入 feather（避免 OOM）。

用法: python download_binance_vision_chunked.py <pair_symbol> <start_YYYYMMDD> <end_YYYYMMDD> <out_feather>
  pair_symbol: BTCUSDT / ETHUSDT / SOLUSDT（合约）
特点：
  - 每下载 CHUNK_DAYS 天合并一次并写入主文件（增量），内存峰值可控
  - 精简列: timestamp, id, side(0/1), price, amount, cost —— 与 freqtrade 兼容
"""
import sys
import os
import zipfile
import tempfile
import datetime as dt
import urllib.request
import time

import pandas as pd

BASE_URL = "https://data.binance.vision/data/futures/um/daily/trades"
CHUNK_DAYS = 20          # 每 20 天合并落盘一次
MAX_DISK_BYTES = 0       # 不限制


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
                    print(f"    下载失败 {url}", flush=True)
                    return None
                time.sleep(2)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(workdir)
        df = pd.read_csv(csv_path, dtype={"id": "int64", "time": "int64"},
                         usecols=["id", "price", "qty", "quote_qty", "time", "is_buyer_maker"])
        out = pd.DataFrame({
            "timestamp": df["time"].to_numpy(),
            "id": df["id"].to_numpy(),
            # side: 0 = sell(买方主动maker), 1 = buy
            "side": (~df["is_buyer_maker"].to_numpy()).astype("int8"),
            "price": df["price"].to_numpy(),
            "amount": df["qty"].to_numpy(),
            "cost": df["quote_qty"].to_numpy(),
        })
        return out
    except Exception as e:
        print(f"    处理失败 {day}: {e}", flush=True)
        return None
    finally:
        for p in (zip_path, csv_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


def load_existing(path: str) -> pd.DataFrame | None:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_feather(path)
        print(f"  已有文件: {len(df)} 条", flush=True)
        return df
    except Exception as e:
        print(f"  已有文件损坏，忽略: {e}", flush=True)
        return None


def main():
    symbol = sys.argv[1]
    start = sys.argv[2]
    end = sys.argv[3]
    out_path = sys.argv[4]

    start_d = dt.datetime.strptime(start, "%Y%m%d").date()
    end_d = dt.datetime.strptime(end, "%Y%m%d").date()

    # 已有文件（增量合并基础）
    existing = load_existing(out_path)

    with tempfile.TemporaryDirectory() as workdir:
        chunk_frames = []
        cur = start_d
        total_new = 0
        while cur <= end_d:
            day_str = cur.strftime("%Y-%m-%d")
            df = download_day(symbol, day_str, workdir)
            if df is not None and len(df) > 0:
                chunk_frames.append(df)
                total_new += len(df)
            cur += dt.timedelta(days=1)

            # 每 CHUNK_DAYS 天或最后一天：合并落盘
            if len(chunk_frames) >= CHUNK_DAYS or cur > end_d:
                if chunk_frames:
                    chunk = pd.concat(chunk_frames, ignore_index=True)
                    chunk = chunk.drop_duplicates(subset="id")
                    if existing is not None:
                        chunk = pd.concat([existing, chunk], ignore_index=True)
                        chunk = chunk.drop_duplicates(subset="id")
                    chunk = chunk.sort_values("timestamp").reset_index(drop=True)
                    chunk.to_feather(out_path)
                    existing = chunk
                    print(f"  落盘: {len(chunk)} 条 (至 {day_str}, 新增累计 {total_new})", flush=True)
                    chunk_frames = []
                    del chunk
                    import gc; gc.collect()

    # 最终校验
    final = pd.read_feather(out_path)
    tmin = dt.datetime.fromtimestamp(final["timestamp"].min()/1000, dt.timezone.utc)
    tmax = dt.datetime.fromtimestamp(final["timestamp"].max()/1000, dt.timezone.utc)
    print(f"✅ 完成: {out_path} {len(final)} 条, {tmin:%Y-%m-%d} ~ {tmax:%Y-%m-%d}", flush=True)


if __name__ == "__main__":
    main()
