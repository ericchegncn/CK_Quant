#!/bin/bash
# 分段下载 3 个主力对的历史 trades 数据（避免单次 OOM）
# 每段 1 个月，串行执行
set -e

BASE_DIR="/d/Eric Cheng/Documents/CK_Quant"
LOG_DIR="/tmp/dl_trades_segments"
mkdir -p "$LOG_DIR"

segments=(
    "20250601-20250701"
    "20250701-20250801"
    "20250801-20250901"
    "20250901-20251001"
    "20251001-20251101"
    "20251101-20251201"
    "20251201-20260101"
)

for seg in "${segments[@]}"; do
    echo "===== 下载段: $seg ====="
    docker run --rm \
        -v "$BASE_DIR/user_data:/CK_Quant/user_data" \
        ck-quant:local download-data \
        --userdir /CK_Quant/user_data \
        --config /CK_Quant/user_data/config_download_top3.json \
        --timeframes 15m \
        --timerange "$seg" \
        --dl-trades \
        --trading-mode futures \
        > "$LOG_DIR/seg_${seg}.log" 2>&1
    code=$?
    if [ $code -ne 0 ]; then
        echo "段 $seg 失败 (exit=$code)，跳过"
        tail -5 "$LOG_DIR/seg_${seg}.log"
    else
        echo "段 $seg 完成"
    fi
done

echo "===== 全部完成，trades 文件汇总 ====="
ls -la "$BASE_DIR/user_data/data/binance/futures/"*trades* 2>/dev/null | awk '{print $5, $9}'
