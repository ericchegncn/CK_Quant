#!/usr/bin/env python
"""优化版：ccxt 直连抓取 Binance 期货 trades，按周写入独立 feather。
使用 fetch_trades 分页，逐对逐周执行，写入独立文件避免大文件内存问题。
"""
import sys
import time
import datetime as dt

import ccxt
import pandas as pd


def fetch_week(ex, pair, start, end):
    """抓取 [start, end) 时间段所有 trades，返回 DataFrame"""
    start_ms = int(dt.datetime.strptime(start, "%Y%m%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    end_ms = int(dt.datetime.strptime(end, "%Y%m%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)

    rows = []
    since = start_ms
    total = 0
    t0 = time.time()
    stall = 0
    while since < end_ms:
        try:
            batch = ex.fetch_trades(pair, since=since, limit=1000)
        except Exception as e:
            stall += 1
            if stall > 5:
                print(f"  连续失败，放弃: {e}", flush=True)
                break
            time.sleep(1)
            continue
        if not batch:
            break
        for t in batch:
            rows.append([t["timestamp"], t["id"], t.get("side"), t["price"], t["amount"]])
        last_ts = batch[-1]["timestamp"]
        total += len(batch)
        if last_ts <= since:
            since += 1000
        else:
            since = last_ts + 1
        stall = 0
        if total % 1000000 < 1000:
            print(f"  {total} 条, 至 {dt.datetime.fromtimestamp(last_ts/1000, dt.timezone.utc)} ({time.time()-t0:.0f}s)", flush=True)
    print(f"  {start}~{end}: {total} 条, 耗时 {time.time()-t0:.0f}s", flush=True)
    if not rows:
        return None
    return pd.DataFrame(rows, columns=["timestamp", "id", "side", "price", "amount"])


def main():
    pair = sys.argv[1]
    start = sys.argv[2]
    end = sys.argv[3]
    out = sys.argv[4]

    ex = ccxt.binance({"options": {"defaultType": "swap"}})
    df = fetch_week(ex, pair, start, end)
    if df is not None:
        df.to_feather(out)
        print(f"  已写入 {out}", flush=True)
    else:
        print(f"  {out} 无数据，跳过", flush=True)


if __name__ == "__main__":
    main()
