#!/usr/bin/env python
"""从 data.binance.vision 批量下载期货 trades 日文件，转换为 freqtrade 格式 feather。

用法: python download_binance_vision.py <pair_symbol> <start_YYYYMMDD> <end_YYYYMMDD> <out_feather>
  pair_symbol: BTCUSDT / ETHUSDT / SOLUSDT（合约）
"""
import sys
import os
import zipfile
import tempfile
import datetime as dt
import urllib.request

import pandas as pd

BASE_URL = "https://data.binance.vision/data/futures/um/daily/trades"
# 合约符号映射到 freqtrade 用的 USDT_USDT 命名
PAIR_MAP = {
    "BTCUSDT": "BTC_USDT_USDT",
    "ETHUSDT": "ETH_USDT_USDT",
    "SOLUSDT": "SOL_USDT_USDT",
}


def download_day(symbol: str, day: str, workdir: str) -> pd.DataFrame | None:
    """下载单日 trades zip，解压并转换为 DataFrame，失败返回 None"""
    url = f"{BASE_URL}/{symbol}/{symbol}-trades-{day}.zip"
    zip_path = os.path.join(workdir, f"{symbol}-trades-{day}.zip")
    csv_path = os.path.join(workdir, f"{symbol}-trades-{day}.csv")
    try:
        # 下载（带重试）
        for attempt in range(3):
            try:
                urllib.request.urlretrieve(url, zip_path)
                break
            except Exception as e:
                if attempt == 2:
                    print(f"    下载失败 {url}: {e}", flush=True)
                    return None
                import time
                time.sleep(2)
        # 解压
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(workdir)
        # 读取
        df = pd.read_csv(csv_path, dtype={"id": "int64", "time": "int64"})
        out = pd.DataFrame({
            "timestamp": df["time"],
            "id": df["id"],
            "type": None,
            "side": df["is_buyer_maker"].map({True: "sell", False: "buy"}),
            "price": df["price"],
            "amount": df["qty"],
            "cost": df["quote_qty"],
        })
        return out
    except Exception as e:
        print(f"    处理失败 {day}: {e}", flush=True)
        return None
    finally:
        # 清理临时文件
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
    out_path = sys.argv[4]

    ft_pair = PAIR_MAP.get(symbol, symbol)
    start_d = dt.datetime.strptime(start, "%Y%m%d").date()
    end_d = dt.datetime.strptime(end, "%Y%m%d").date()

    # 检查已有文件（合并模式）
    existing = None
    if os.path.exists(out_path):
        try:
            existing = pd.read_feather(out_path)
            print(f"已有文件: {len(existing)} 条, "
                  f"{dt.datetime.fromtimestamp(existing['timestamp'].min()/1000, dt.timezone.utc):%Y-%m-%d} ~ "
                  f"{dt.datetime.fromtimestamp(existing['timestamp'].max()/1000, dt.timezone.utc):%Y-%m-%d}", flush=True)
        except Exception as e:
            print(f"已有文件读取失败: {e}", flush=True)

    with tempfile.TemporaryDirectory() as workdir:
        all_frames = []
        cur = start_d
        days = (end_d - start_d).days + 1
        n = 0
        while cur <= end_d:
            day_str = cur.strftime("%Y-%m-%d")
            df = download_day(symbol, day_str, workdir)
            if df is not None and len(df) > 0:
                all_frames.append(df)
                n += len(df)
            cur += dt.timedelta(days=1)
            if n % 5000000 < 2000000 and n > 0:
                print(f"  累计 {n} 条 (至 {day_str})", flush=True)
        if not all_frames:
            print("无数据下载", flush=True)
            return

    merged = pd.concat(all_frames, ignore_index=True)
    # 去重排序
    merged = merged.drop_duplicates(subset="id").sort_values("timestamp").reset_index(drop=True)
    # 与已有文件合并
    if existing is not None and len(existing) > 0:
        merged = pd.concat([existing, merged], ignore_index=True)
        merged = merged.drop_duplicates(subset="id").sort_values("timestamp").reset_index(drop=True)
        print(f"合并后总计: {len(merged)} 条", flush=True)
    merged.to_feather(out_path)
    print(f"已写入 {out_path}: {len(merged)} 条, "
          f"{dt.datetime.fromtimestamp(merged['timestamp'].min()/1000, dt.timezone.utc):%Y-%m-%d} ~ "
          f"{dt.datetime.fromtimestamp(merged['timestamp'].max()/1000, dt.timezone.utc):%Y-%m-%d}", flush=True)


if __name__ == "__main__":
    main()
