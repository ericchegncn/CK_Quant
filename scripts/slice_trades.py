#!/usr/bin/env python
"""从完整 trades 文件提取指定时间区间，生成小文件用于回测（避免大文件 OOM）。
流式读取+过滤+写入，内存恒定。
用法: python slice_trades.py <input> <start_ms> <end_ms> <output>
"""
import sys
import datetime as dt

import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc

COLS = ["timestamp", "id", "type", "side", "price", "amount", "cost"]


def main():
    inp, start_ms, end_ms, outp = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]

    reader = ipc.RecordBatchFileReader(inp)
    n = reader.num_record_batches
    writer = None
    total = 0
    for i in range(n):
        batch = reader.get_batch(i).to_pandas()
        mask = (batch["timestamp"] >= start_ms) & (batch["timestamp"] < end_ms)
        sub = batch[mask]
        if len(sub):
            tbl = pa.Table.from_pandas(sub[COLS], preserve_index=False)
            if writer is None:
                writer = pa.ipc.new_file(outp, tbl.schema)
            writer.write_table(tbl)
            total += len(sub)
        del batch, sub
    if writer:
        writer.close()

    s = dt.datetime.fromtimestamp(start_ms/1000, dt.timezone.utc).strftime("%Y-%m-%d")
    e = dt.datetime.fromtimestamp(end_ms/1000, dt.timezone.utc).strftime("%Y-%m-%d")
    print(f"✅ {outp}: {total} 条 ({s} ~ {e})", flush=True)


if __name__ == "__main__":
    main()
