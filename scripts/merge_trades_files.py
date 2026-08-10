#!/usr/bin/env python
"""合并分块 trades 文件为 freqtrade 标准格式的单一 trades 文件。
流式拼接（不做全局去重/排序——主文件与分块文件时间不重叠，freqtrade 按 candle_start 分组不要求排序）。
用法: python merge_trades_files.py <symbol_prefix> <out_path>
"""
import sys
import os
import glob
import datetime as dt

import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc

COLS = ["timestamp", "id", "type", "side", "price", "amount", "cost"]


def fix_early(batch: pd.DataFrame) -> pd.DataFrame:
    """早期 0/1 side 文件转标准格式"""
    side_arr = np.where(batch["side"].to_numpy() == 0, "sell", "buy")
    return pd.DataFrame({
        "timestamp": batch["timestamp"].astype("int64"),
        "id": batch["id"].astype(str),
        "type": None,
        "side": side_arr,
        "price": batch["price"].astype("float64"),
        "amount": batch["amount"].astype("float64"),
        "cost": batch["cost"].astype("float64"),
    })


def main():
    prefix = sys.argv[1]
    out_path = sys.argv[2]
    out_dir = os.path.dirname(out_path)
    extra_dir = os.path.join(out_dir, "trades_extra")

    candidates = []
    # 已转格式的主文件（如 BTC_USDT_USDT-trades-fixed.feather）
    fixed_main = os.path.join(out_dir, f"{prefix}_USDT_USDT-trades-fixed.feather")
    if os.path.exists(fixed_main):
        candidates.append(fixed_main)
    candidates += sorted(glob.glob(os.path.join(extra_dir, f"{prefix}*.feather")))

    if not candidates:
        print("没有可合并的文件", flush=True)
        sys.exit(1)

    print(f"将合并 {len(candidates)} 个文件:", flush=True)
    for c in candidates:
        print(f"  {os.path.basename(c)}", flush=True)

    writer = None
    total = 0
    for c in candidates:
        reader = ipc.RecordBatchFileReader(c)
        n = reader.num_record_batches
        for i in range(n):
            batch = reader.get_batch(i).to_pandas()
            if "side" in batch.columns and batch["side"].dtype != object and batch["side"].dtype != "string":
                # side 是 0/1
                batch = fix_early(batch)
            elif set(batch.columns) != set(COLS):
                batch = fix_early(batch)
            batch = batch[COLS]
            tbl = pa.Table.from_pandas(batch, preserve_index=False)
            if writer is None:
                writer = pa.ipc.new_file(out_path, tbl.schema)
            writer.write_table(tbl)
            total += len(batch)
            del batch, tbl
        print(f"  完成 {os.path.basename(c)}, 累计 {total}", flush=True)

    if writer:
        writer.close()

    check = pd.read_feather(out_path)
    tmin = dt.datetime.fromtimestamp(check["timestamp"].min()/1000, dt.timezone.utc)
    tmax = dt.datetime.fromtimestamp(check["timestamp"].max()/1000, dt.timezone.utc)
    print(f"✅ {out_path}: {len(check)} 条, {tmin:%Y-%m-%d} ~ {tmax:%Y-%m-%d}, side {check['side'].head(2).tolist()}", flush=True)


if __name__ == "__main__":
    main()
