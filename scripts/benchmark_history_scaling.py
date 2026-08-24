#!/usr/bin/env python3
"""Reproducible SQLite history benchmark for CK Quant.

The source database is opened through SQLite's backup API and is never modified.
Synthetic rows are written only to a temporary database which is deleted on exit.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
from pathlib import Path


def timed(label: str, callback):
    started = time.perf_counter()
    value = callback()
    elapsed = time.perf_counter() - started
    print(f"{label}: {elapsed:.3f}s")
    return value, elapsed


def clone_and_expand(source: Path, target: Path, synthetic_trades: int) -> None:
    source_conn = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    target_conn = sqlite3.connect(target)
    source_conn.backup(target_conn)
    source_conn.close()

    target_conn.execute("PRAGMA foreign_keys=OFF")
    target_conn.execute("PRAGMA journal_mode=OFF")
    trade_columns = [row[1] for row in target_conn.execute("PRAGMA table_info(trades)")]
    order_columns = [row[1] for row in target_conn.execute("PRAGMA table_info(orders)")]
    trade = list(target_conn.execute("SELECT * FROM trades WHERE is_open = 0 LIMIT 1").fetchone())
    trade_id_index = trade_columns.index("id")
    pair_index = trade_columns.index("pair")
    template_trade_id = trade[trade_id_index]
    orders = [
        list(row)
        for row in target_conn.execute(
            "SELECT * FROM orders WHERE ft_trade_id = ?", (template_trade_id,)
        )
    ]
    if not orders:
        raise RuntimeError("The selected closed trade has no orders to clone.")

    order_id_index = order_columns.index("id")
    order_trade_index = order_columns.index("ft_trade_id")
    exchange_order_id_index = order_columns.index("order_id")
    order_pair_index = order_columns.index("ft_pair")
    next_trade_id = target_conn.execute("SELECT coalesce(max(id), 0) + 1 FROM trades").fetchone()[0]
    next_order_id = target_conn.execute("SELECT coalesce(max(id), 0) + 1 FROM orders").fetchone()[0]
    trade_sql = (
        f"INSERT INTO trades ({','.join(trade_columns)}) "
        f"VALUES ({','.join('?' for _ in trade_columns)})"
    )
    order_sql = (
        f"INSERT INTO orders ({','.join(order_columns)}) "
        f"VALUES ({','.join('?' for _ in order_columns)})"
    )

    for batch_start in range(0, synthetic_trades, 1000):
        trade_rows = []
        order_rows = []
        for offset in range(batch_start, min(batch_start + 1000, synthetic_trades)):
            trade_id = next_trade_id + offset
            pair = f"PERF{offset % 20}/USDT"
            trade_row = trade.copy()
            trade_row[trade_id_index] = trade_id
            trade_row[pair_index] = pair
            trade_rows.append(trade_row)
            for order_offset, template_order in enumerate(orders):
                order_row = template_order.copy()
                order_row[order_id_index] = next_order_id
                next_order_id += 1
                order_row[order_trade_index] = trade_id
                order_row[exchange_order_id_index] = f"perf-{trade_id}-{order_offset}"
                order_row[order_pair_index] = pair
                order_rows.append(order_row)
        target_conn.executemany(trade_sql, trade_rows)
        target_conn.executemany(order_sql, order_rows)
        target_conn.commit()
    target_conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_trade_status_filled "
        "ON orders(ft_trade_id,status,order_filled_date)"
    )
    target_conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_trades_open_close_id ON trades(is_open,close_date,id)"
    )
    target_conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_trades_open_short_close "
        "ON trades(is_open,is_short,close_date)"
    )
    target_conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_trades_open_closed_profit "
        "ON trades(is_open,close_profit_abs)"
    )
    target_conn.execute("PRAGMA journal_mode=WAL")
    target_conn.close()


def benchmark(database: Path) -> None:
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    closed = conn.execute("SELECT count(*) FROM trades WHERE is_open = 0").fetchone()[0]
    orders = conn.execute("SELECT count(*) FROM orders").fetchone()[0]
    print(f"dataset: {closed:,} closed trades, {orders:,} orders")

    def old_history():
        trade_rows = [dict(row) for row in conn.execute("SELECT * FROM trades WHERE is_open = 0")]
        order_rows = [
            dict(row)
            for row in conn.execute(
                "SELECT o.* FROM orders o JOIN trades t ON t.id=o.ft_trade_id WHERE t.is_open=0"
            )
        ]
        return len(json.dumps({"trades": trade_rows, "orders": order_rows}, default=str))

    def latest_history():
        rows = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM trades WHERE is_open=0 ORDER BY close_date DESC LIMIT 500"
            )
        ]
        return len(json.dumps({"trades": rows}, default=str))

    compact_sql = """
        SELECT t.id,t.pair,t.is_short,t.open_date,t.close_date,t.close_profit,
               t.close_profit_abs,coalesce(v.volume,0) AS trading_volume
        FROM trades t
        LEFT JOIN (
            SELECT ft_trade_id,sum(cost) AS volume FROM orders
            WHERE status='closed' GROUP BY ft_trade_id
        ) v ON v.ft_trade_id=t.id
        WHERE t.is_open=0 AND t.close_date IS NOT NULL
        ORDER BY t.close_date,t.id
    """
    old_bytes, _ = timed("old full history + orders", old_history)
    latest_bytes, _ = timed("newest 500 without orders", latest_history)
    _, _ = timed("compact statistics cold snapshot", lambda: conn.execute(compact_sql).fetchall())
    _, _ = timed(
        "compact statistics cache watermark",
        lambda: conn.execute(
            "SELECT close_date,id FROM trades WHERE is_open=0 AND close_date IS NOT NULL "
            "ORDER BY close_date DESC,id DESC LIMIT 1"
        ).fetchone(),
    )
    print(f"serialized history: {old_bytes / 1024 / 1024:.1f} MiB -> {latest_bytes / 1024:.1f} KiB")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--trades", type=int, default=30_000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ck-quant-perf-") as temp_dir:
        target = Path(temp_dir) / "benchmark.sqlite"
        clone_and_expand(args.source.resolve(), target, args.trades)
        benchmark(target)


if __name__ == "__main__":
    main()
