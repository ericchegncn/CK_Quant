# Synthetic Iceberg Orders (冰山单)

CK Quant 提供**合成冰山单**（synthetic iceberg execution）—— 把一笔大订单拆成多个
小订单（child orders），交易所同一时刻只能看到一个子单，前一片成交后再补下一片，
从而隐藏真实交易意图，减少大单对盘口的冲击。

真正的交易所原生冰山单只有少数平台支持。CK Quant 在**软件层面模拟**这一行为，
因此称为 *synthetic* iceberg。

## 工作机制

```text
目标：买入 10,000 USDT 的 BTC
visible_ratio = 0.1, max_slices = 10

第 1 片：1,000 USDT（10%）  ──→ 交易所只看到这一个单
  ↓ 成交
第 2 片：1,000 USDT（10%）  ──→ 5 秒后（replenish_interval）补上
  ↓ 成交
... 直到总目标完成（最多 10 片）
```

### 入场（entry）

- 策略入场信号产生时，目标仓位记录在交易的 custom_data（`ckq_iceberg_entry`）
- 首单只下 `总金额 × visible_ratio`
- 成交后由 `process_iceberg_orders()`（每个 bot loop tick 调用）检查间隔，
  满足 `replenish_interval` 后补下一片，直到总目标完成

### 出场（exit）

- 仅在 **EXIT_SIGNAL / CUSTOM_EXIT** 出场时拆分（止损、ROI、强制平仓**不拆分**，
  保证快速离场优先）
- 同样一片片卖出，每片间隔 `replenish_interval`

### 状态持久化

- 总目标金额存放在**本地交易数据库**（trade 的 custom_data 字段），
  机器人重启后不会丢失未完成的冰山计划 —— 与 CK Quant 的 crash-safe
  订单恢复设计一致

## 配置

在 `config.json` 中添加 `iceberg_orders` 段：

```json
{
    "iceberg_orders": {
        "enabled": true,
        "entry": true,
        "exit": true,
        "visible_ratio": 0.1,
        "max_slices": 10,
        "min_slice_stake": 0.0,
        "replenish_interval": 5.0,
        "size_jitter": 0.0
    }
}
```

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `enabled` | `false` | 总开关。关闭时冰山单完全不生效 |
| `entry` | `true` | 入场是否拆分 |
| `exit` | `true` | 出场是否拆分 |
| `visible_ratio` | `0.1` | 每个子单占**总目标金额**的比例（0~1）。`0.1` = 每片 10% |
| `max_slices` | `10` | 最多拆分数（2~100），**硬上限**，防止无限拆单 |
| `min_slice_stake` | `0.0` | 子单最小金额（USDT）。防止拆出过小的碎片单 |
| `replenish_interval` | `5.0` | 上一片成交后到补下一片的间隔（秒） |
| `size_jitter` | `0.0` | 子单大小随机扰动（0~0.5，即 0~50%）。让每片大小略有差异，避免被识别出固定模式的冰山 |

> 实际子单大小 = `max(总金额 × visible_ratio, 总金额 / max_slices, min_slice_stake)`，
> 再乘以 `(1 + 随机(0, size_jitter))`，且不超过剩余金额。

## 适用场景

- **大资金**：单笔 stake 较大，直接下单会显著冲击盘口时
- **流动性差的交易对**：盘口薄、大单容易被察觉
- **隐藏建仓/平仓意图**：不希望对手盘看到你的真实目标

## 注意事项

1. **回测不模拟冰山单** —— 回测无法模拟逐片成交对盘口的影响，这是**实盘特性**
2. 拆分会增加订单数量，但**总手续费不变**（总成交金额相同）
3. 每片之间有 `replenish_interval` 延迟，整体成交速度变慢 —— 对追求快速
   进场的策略，建议保持关闭或调大 `visible_ratio`
4. 需要交易所支持子单粒度下单（Binance 期货等主流交易所均可）

## 配置建议

- **小仓位**（单笔 < 总资金的 10%）：建议保持 `enabled: false`（默认），
  冰山单收益有限且拖慢成交
- **大仓位**（单笔 ≥ 总资金的 10~20%）：开启并把 `visible_ratio` 调到
  `0.2 ~ 0.3`（比默认 0.1 激进，减少片数、加快完成），
  `replenish_interval` 用 `3~5` 秒
- 流动性差的小币种交易对：可单独调小 `visible_ratio`（0.05~0.1）+ 开启
  `size_jitter`（0.1~0.2）隐藏模式

## 代码位置

- 配置与切片逻辑：`freqtrade/ck_quant/iceberg.py`
- 订单执行与补单循环：`freqtrade/freqtradebot.py`
  （`_iceberg_entry_slice` / `_iceberg_exit_slice` / `process_iceberg_orders`）
- 配置 schema：`freqtrade/config_schema/config_schema.py`（`iceberg_orders`）
