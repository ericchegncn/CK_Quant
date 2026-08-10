#!/bin/bash
# 单对 × 单月 分段下载 trades（内存安全，避免 OOM）
# BTC 已下载 2025-07；此脚本补全 BTC/ETH/SOL 的 2025-08 ~ 2026-01
set -e

BASE_DIR="/d/Eric Cheng/Documents/CK_Quant"
LOG_DIR="/tmp/dl_trades_single"
mkdir -p "$LOG_DIR"

pairs=("BTC/USDT:USDT" "ETH/USDT:USDT" "SOL/USDT:USDT")

segments=(
    "20250801-20250901"
    "20250901-20251001"
    "20251001-20251101"
    "20251101-20251201"
    "20251201-20260101"
)

for pair in "${pairs[@]}"; do
    for seg in "${segments[@]}"; do
        fname=$(echo "$pair" | tr '/:' '__')
        echo "===== $pair $seg ====="
        docker run --rm \
            -v "$BASE_DIR/user_data:/CK_Quant/user_data" \
            ck-quant:local download-data \
            --userdir /CK_Quant/user_data \
            --config /CK_Quant/user_data/config_dl_single.json \
            --pairs "$pair" \
            --timeframes 15m \
            --timerange "$seg" \
            --dl-trades \
            --trading-mode futures \
            > "$LOG_DIR/${fname}_${seg}.log" 2>&1
        code=$?
        if [ $code -ne 0 ]; then
            echo "  失败 (exit=$code)"
            grep -iE "error|memory|killed" "$LOG_DIR/${fname}_${seg}.log" | tail -3
        else
            # 检查是否真的下载到数据
            if grep -q "earlier than available\|no data" "$LOG_DIR/${fname}_${seg}.log"; then
                echo "  无新数据（交易所范围外）"
            else
                echo "  完成"
            fi
        fi
    done
done

echo "===== 全部完成，trades 文件汇总 ====="
ls -la "$BASE_DIR/user_data/data/binance/futures/"*trades* 2>/dev/null | awk '{print $5, $9}'
