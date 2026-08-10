#!/usr/bin/env python
"""将 vision 早期下载的 trades（side 0/1）转换为 freqtrade 标准格式（side sell/buy, id str, type 列）。
使用 RecordBatchFileReader 流式读取 + RecordBatchFileWriter 流式写入，内存恒定。
用法: python fix_trades_format.py <input> <output>
"""
import sys
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.feather as pf
import pyarrow.ipc as ipc

COLS = ["timestamp", "id", "type", "side", "price", "amount", "cost"]


def fix_chunk(df: pd.DataFrame) -> pd.DataFrame:
    side_arr = np.where(df["side"].to_numpy() == 0, "sell", "buy")
    return pd.DataFrame({
        "timestamp": df["timestamp"].to_numpy().astype("int64"),
        "id": df["id"].astype(str).to_numpy(),
        "type": None,
        "side": side_arr,
        "price": df["price"].to_numpy().astype("float64"),
        "amount": df["amount"].to_numpy().astype("float64"),
        "cost": df["cost"].to_numpy().astype("float64"),
    })[COLS]


def main():
    inp, outp = sys.argv[1], sys.argv[2]

    reader = ipc.RecordBatchFileReader(inp)
    schema = reader.schema
    n_batches = reader.num_record_batches
    print(f"输入 {inp}: {n_batches} 个 batch, schema 列 {schema.names}", flush=True)

    writer = None
    done = 0
    for i in range(n_batches):
        batch = reader.get_batch(i).to_pandas()
        fixed = fix_chunk(batch)
        tbl = pa.Table.from_pandas(fixed, preserve_index=False)
        if writer is None:
            writer = pa.ipc.new_file(outp, tbl.schema)
        writer.write_table(tbl)
        done += len(fixed)
        if i % 5 == 0:
            print(f"  已转换 {done} 条 (batch {i}/{n_batches})", flush=True)
        del batch, fixed, tbl

    if writer:
        writer.close()

    check = pd.read_feather(outp)
    print(f"✅ 输出 {outp}: {len(check)} 条, side 样例 {check['side'].head(3).tolist()}", flush=True)


if __name__ == "__main__":
    main()
