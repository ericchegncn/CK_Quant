# Tick-Level Backtest (tick 级回测)

CK Quant 提供 **tick 级回测引擎** —— 用真实逐笔成交数据（tick）撮合出场，
解决 freqtrade 原版 OHLCV 回测的精度问题。

## 为什么需要它

freqtrade 原版回测用 15m bar 的 `high/low` 判断止损/止盈是否触发，但 **K 线内部
的价格路径是未知的**：

```text
同一根 15m bar，两种完全不同的路径：
  路径A：开 → 冲高 → 回落 → 收   （先触及止盈，后触及止损）
  路径B：开 → 杀跌 → 反弹 → 收   （先触及止损，后触及止盈）

OHLCV 回测只能用 high/low 判断"都被触及"，但不知道谁先谁后 —— 只能假设。
```

**实测证据**（ETH 2025-07，0.5% 止损）：
- **7.1% 的交易触发顺序判断错误**（OHLCV 认为先止盈，真实 tick 是先止损）
- 错误是**系统性偏向乐观**：OHLCV 总盈亏 +0.01，真实 tick 总盈亏 -0.01
- 止损越紧（距离越小），误差越大 —— 这正是紧止损策略回测虚高的原因

## 核心设计（内存友好）

| 特性 | 说明 |
|---|---|
| 分块加载 | tick 数据按周切分（feather），一次只加载一个 chunk |
| 流式撮合 | 逐 chunk 处理 tick，处理完立即释放内存 |
| 峰值内存 | 只与单个 chunk 相关（ETH 一周 ≈ 2GB），15GB 笔记本可跑 |
| 策略复用 | 信号在聚合的 15m bar 上计算，复用 `populate_indicators` / `populate_entry_trend` |
| 真实时序 | 信号确认后**立即按当前 tick 入场**（而非 freqtrade 的"下一根 bar 开盘"） |
| tick 采样 | `--tick-stride` 控制采样密度，平衡速度与精度 |

## 数据准备

Binance 期货逐笔成交历史（约 1 年），从 binance.vision 按日下载，按周聚合：

```bash
python scripts/download_vision_chunked.py ETHUSDT 20250701 20250731 \
    user_data/data/binance/futures/trades_eth
```

输出：`user_data/data/binance/futures/trades_eth/ETHUSDT_20250701_20250707.feather`（每周一个文件）

## 用法

```bash
python -m freqtrade.ck_quant.tick_backtest \
    --config user_data/config.json \
    --strategy MyPrivateStrategy \
    --data-dir user_data/data/binance/futures/trades_eth \
    --timerange 20250701-20250731 \
    --pair "ETH/USDT:USDT" \
    --stoploss 0.005 \
    --takeprofit 0.005
```

### 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--config` | 必填 | freqtrade 配置文件（含交易对白名单） |
| `--strategy` | 必填 | 策略类名（复用其入场信号） |
| `--data-dir` | 必填 | tick feather 文件目录 |
| `--timerange` | `20250701-20250731` | 回测区间 `YYYYMMDD-YYYYMMDD` |
| `--pair` | `ETH/USDT:USDT` | 回测交易对 |
| `--stoploss` | `0.005` | 止损比例（相对入场价） |
| `--takeprofit` | `0.005` | 止盈比例（1:1 盈亏比时与止损相同） |
| `--tick-stride` | `50` | 每 N 个 tick 处理一个。`50` ≈ 处理 2% 的 tick（快）；`1` = 全量（慢但最精确） |

## 输出

```
[tick] 找到 5 个分块: ETHUSDT_20250701_20250707.feather ~ ETHUSDT_20250729_20250731.feather
[tick] 聚合 2976 根 15m bars

=== Tick 回测结果 ===
总交易: 10
胜: 5  负: 5  胜率: 50.0%
总盈亏(每单1单位): +0.0000
出场: 止损 5  止盈 5  其他 0
```

每笔交易明细：方向、入场价、出场原因（stop_loss / take_profit）、出场价、盈亏。

## 与 freqtrade 原版回测的差异

| | tick 引擎 | freqtrade OHLCV |
|---|---|---|
| 入场时机 | 信号 bar 内 tick 确认后立即入场 | **下一根 bar 开盘**（滞后最多 15m） |
| 出场触发 | 真实 tick 序列逐笔判断顺序 | bar high/low 假设（同 bar 双触发时猜） |
| 触发价格 | 精确 tick 价格 | bar high/low 或开盘价近似 |
| 适合 | 紧止损、盘中信号、精确验证 | 宽止损、粗略评估 |

## 已知限制

- 当前为**独立引擎**（不修改 freqtrade 主回测循环），输出格式与 freqtrade
  回测报告不同（后续可扩展为统一报告）
- 入场语义是"信号确认后立即入场"，与 freqtrade 的"下一根 bar"不同 ——
  对比两个引擎结果时注意时序口径差异
- 尚未支持：杠杆/保证金、动态止损、多对同时回测（规划中）

## 代码位置

- `freqtrade/ck_quant/tick_backtest.py` —— 引擎主体
- `scripts/tick_match_proto.py` —— 精度验证原型（OHLCV vs tick 对照实验）
- `scripts/download_vision_chunked.py` —— tick 数据下载管线
