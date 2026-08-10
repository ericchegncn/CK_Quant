#!/bin/bash
# 带重试的周分段下载（每次失败自动重试，最多 6 次）
set -e

BASE_DIR="/d/Eric Cheng/Documents/CK_Quant"
LOG_DIR="/tmp/dl_retry"
mkdir -p "$LOG_DIR"

# BTC 从 2025-09-16 续；ETH/SOL 从 07-01 全量
jobs=(
    "BTC/USDT:USDT|20250916-20250923"
    "BTC/USDT:USDT|20250923-20250930"
    "BTC/USDT:USDT|20250930-20251007"
    "BTC/USDT:USDT|20251007-20251014"
    "BTC/USDT:USDT|20251014-20251021"
    "BTC/USDT:USDT|20251021-20251028"
    "BTC/USDT:USDT|20251028-20251104"
    "BTC/USDT:USDT|20251104-20251111"
    "BTC/USDT:USDT|20251111-20251118"
    "BTC/USDT:USDT|20251118-20251125"
    "BTC/USDT:USDT|20251125-20251202"
    "BTC/USDT:USDT|20251202-20251209"
    "BTC/USDT:USDT|20251209-20251216"
    "BTC/USDT:USDT|20251216-20251223"
    "BTC/USDT:USDT|20251223-20260101"
    "ETH/USDT:USDT|20250701-20250708"
    "ETH/USDT:USDT|20250708-20250715"
    "ETH/USDT:USDT|20250715-20250722"
    "ETH/USDT:USDT|20250722-20250729"
    "ETH/USDT:USDT|20250729-20250805"
    "ETH/USDT:USDT|20250805-20250812"
    "ETH/USDT:USDT|20250812-20250819"
    "ETH/USDT:USDT|20250819-20250826"
    "ETH/USDT:USDT|20250826-20250902"
    "ETH/USDT:USDT|20250902-20250909"
    "ETH/USDT:USDT|20250909-20250916"
    "ETH/USDT:USDT|20250916-20250923"
    "ETH/USDT:USDT|20250923-20250930"
    "ETH/USDT:USDT|20250930-20251007"
    "ETH/USDT:USDT|20251007-20251014"
    "ETH/USDT:USDT|20251014-20251021"
    "ETH/USDT:USDT|20251021-20251028"
    "ETH/USDT:USDT|20251028-20251104"
    "ETH/USDT:USDT|20251104-20251111"
    "ETH/USDT:USDT|20251111-20251118"
    "ETH/USDT:USDT|20251118-20251125"
    "ETH/USDT:USDT|20251125-20251202"
    "ETH/USDT:USDT|20251202-20251209"
    "ETH/USDT:USDT|20251209-20251216"
    "ETH/USDT:USDT|20251216-20251223"
    "ETH/USDT:USDT|20251223-20260101"
    "SOL/USDT:USDT|20250701-20250708"
    "SOL/USDT:USDT|20250708-20250715"
    "SOL/USDT:USDT|20250715-20250722"
    "SOL/USDT:USDT|20250722-20250729"
    "SOL/USDT:USDT|20250729-20250805"
    "SOL/USDT:USDT|20250902-20250909"
    "SOL/USDT:USDT|20250909-20250916"
    "SOL/USDT:USDT|20250916-20250923"
    "SOL/USDT:USDT|20250923-20250930"
    "SOL/USDT:USDT|20250930-20251007"
    "SOL/USDT:USDT|20251007-20251014"
    "SOL/USDT:USDT|20251014-20251021"
    "SOL/USDT:USDT|20251021-20251028"
    "SOL/USDT:USDT|20251028-20251104"
    "SOL/USDT:USDT|20251104-20251111"
    "SOL/USDT:USDT|20251111-20251118"
    "SOL/USDT:USDT|20251118-20251125"
    "SOL/USDT:USDT|20251125-20251202"
    "SOL/USDT:USDT|20251202-20251209"
    "SOL/USDT:USDT|20251209-20251216"
    "SOL/USDT:USDT|20251216-20251223"
    "SOL/USDT:USDT|20251223-20260101"
)

for job in "${jobs[@]}"; do
    pair="${job%%|*}"
    seg="${job##*|}"
    fname=$(echo "$pair" | tr '/:' '__')
    ok=0
    for attempt in 1 2 3 4 5 6; do
        echo "===== $pair $seg (尝试 $attempt/6) ====="
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
            > "$LOG_DIR/${fname}_${seg}_a${attempt}.log" 2>&1
        code=$?
        if [ $code -eq 0 ]; then
            echo "  完成 (attempt $attempt)"
            ok=1
            break
        fi
        echo "  失败 (exit=$code)，重试..."
        sleep 5
    done
    if [ $ok -eq 0 ]; then
        echo "  !! $pair $seg 重试6次仍失败"
    fi
done

echo "===== 全部完成 ====="
ls -la "$BASE_DIR/user_data/data/binance/futures/"*trades* 2>/dev/null | awk '{print $5, $9}'
