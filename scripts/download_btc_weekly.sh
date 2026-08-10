#!/bin/bash
# BTC 按周分段下载（数据量小，避免 Docker Desktop 限制）
set -e

BASE_DIR="/d/Eric Cheng/Documents/CK_Quant"
LOG_DIR="/tmp/dl_btc_weekly"
mkdir -p "$LOG_DIR"

# BTC: 2025-07-01 起（交易所最早可用），补 7月~次年1月，按周
# 每周一段：YYYYMMDD-YYYYMMDD（+7天）
weeks=(
    "20250701-20250708"
    "20250708-20250715"
    "20250715-20250722"
    "20250722-20250729"
    "20250729-20250805"
    "20250805-20250812"
    "20250812-20250819"
    "20250819-20250826"
    "20250826-20250902"
    "20250902-20250909"
    "20250909-20250916"
    "20250916-20250923"
    "20250923-20250930"
    "20250930-20251007"
    "20251007-20251014"
    "20251014-20251021"
    "20251021-20251028"
    "20251028-20251104"
    "20251104-20251111"
    "20251111-20251118"
    "20251118-20251125"
    "20251125-20251202"
    "20251202-20251209"
    "20251209-20251216"
    "20251216-20251223"
    "20251223-20251230"
    "20251230-20260101"
)

for seg in "${weeks[@]}"; do
    echo "===== BTC $seg ====="
    docker run --rm \
        -v "$BASE_DIR/user_data:/CK_Quant/user_data" \
        ck-quant:local download-data \
        --userdir /CK_Quant/user_data \
        --config /CK_Quant/user_data/config_dl_single.json \
        --pairs "BTC/USDT:USDT" \
        --timeframes 15m \
        --timerange "$seg" \
        --dl-trades \
        --trading-mode futures \
        > "$LOG_DIR/btc_${seg}.log" 2>&1
    code=$?
    if [ $code -ne 0 ]; then
        echo "  段 $seg 失败 (exit=$code)"
    else
        echo "  完成"
    fi
done

echo "===== 全部完成 ====="
ls -la "$BASE_DIR/user_data/data/binance/futures/"*trades* 2>/dev/null | awk '{print $5, $9}'
