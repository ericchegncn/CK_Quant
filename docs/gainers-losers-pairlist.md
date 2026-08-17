# GainersLosersPairList — 涨跌幅排名交易对模式

CK Quant 新增的 **涨跌幅排名** 交易对选择模式，支持：
- 按 24h 涨跌幅（或自定义回看周期）选择 **涨幅榜 + 跌幅榜** 交易对
- 涨幅/跌幅数量**独立配置**（如涨幅前 5 + 跌幅前 3）
- **两种工作模式**：原生过滤链（filter）或混合并集（union）
- 与 VolumePairList / StaticPairList **自由组合**

---

## 一、为什么需要它？

默认的 `VolumePairList`（成交额排名）选的是"交易量大"的币 —— 大市值、流动性好，但也意味着**波动小、趋势弱**。

**涨跌幅排名**关注的是"今天涨得最猛 / 跌得最狠"的币 —— 这些才是趋势交易（如 CK_Trend 系列）最感兴趣的标的：
- **涨幅榜**：强势币，顺势做多机会
- **跌幅榜**：超跌币，反弹/做空机会

---

## 二、配置参数

在 `config.json` 的 `pairlists` 数组中加入：

```jsonc
{
    "method": "GainersLosersPairList",
    "gainers_count": 5,          // 涨幅榜选前 5 个
    "losers_count": 3,           // 跌幅榜选前 3 个
    "direction": "both",         // both=涨跌都选 / gainers=只选涨幅 / losers=只选跌幅
    "mode": "union",             // union=混合并集 / filter=原生过滤链
    "refresh_period": 1800       // 刷新间隔（秒），默认 1800（30 分钟）
}
```

### 参数说明

| 参数 | 默认值 | 说明 |
|---|---|---|
| `gainers_count` | 无 | 涨幅榜数量（与 losers_count 独立） |
| `losers_count` | 无 | 跌幅榜数量 |
| `number_assets` | 无 | 兼容参数：涨幅跌幅同数（设了它就不用 gainers/losers_count） |
| `direction` | `both` | `both` / `gainers` / `losers` |
| `mode` | `filter` | `filter`（原生过滤链）/ `union`（混合并集） |
| `refresh_period` | 1800 | 刷新间隔秒数 |
| `min_value` / `max_value` | 无 | 涨跌幅过滤范围（如只选涨幅 > 5% 的） |
| `lookback_days` | 0 | 用历史K线算涨跌幅（0=用 24h ticker） |
| `lookback_period` + `lookback_timeframe` | 0 / 1d | 回看 N 根 K 线（如 7 根 1d = 近 7 天涨跌幅） |

---

## 三、两种模式（关键概念）

### mode: "filter"（原生过滤链）

**freqtrade 默认行为**：多个 pairlist 串联，后一个**只在上一个的输出里筛选**。

```jsonc
"pairlists": [
    { "method": "VolumePairList", "number_assets": 5 },
    { "method": "GainersLosersPairList", "gainers_count": 5, "losers_count": 3 }
]
```
→ Volume 先选 5 个成交额最大的 → 涨跌幅**只在这 5 个里**排名 → 结果 ≤ 5 个。
（适用于：先过滤出高流动性池子，再从中挑涨跌幅）

### mode: "union"（混合并集）⭐ 推荐

**CK Quant 增强**：涨跌幅排名**独立从全市场选择**，然后与前面的结果**合并（并集去重）**。

```jsonc
"pairlists": [
    { "method": "VolumePairList", "number_assets": 5 },          // 成交额 top5
    {
        "method": "GainersLosersPairList",
        "gainers_count": 5, "losers_count": 3,
        "mode": "union"                                          // 涨幅 top5 + 跌幅 top3
    },
    { "method": "StaticPairList" }                               // 静态 3 对（追加）
]
```
→ 最终白名单 = **成交额 5 + 涨幅 5 + 跌幅 3 + 静态 3 = 最多 16 对**（重复的自动去重）。
（适用于：想要"什么都有一点"的混合池子）

---

## 四、完整配置示例

### 示例 1：纯涨跌幅（涨幅前10 + 跌幅前10）

```jsonc
"pairlists": [
    {
        "method": "GainersLosersPairList",
        "number_assets": 10,
        "direction": "both",
        "mode": "union"
    }
]
```

### 示例 2：混合模式（成交额 top5 + 涨幅 top5 + 跌幅 top3 + 静态 3 对）

```jsonc
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 5,
        "sort_key": "quoteVolume",
        "min_value": 0
    },
    {
        "method": "GainersLosersPairList",
        "gainers_count": 5,
        "losers_count": 3,
        "direction": "both",
        "mode": "union"
    },
    { "method": "StaticPairList" }   // 静态对来自 exchange.pair_whitelist
]
```

### 示例 3：近 7 天涨跌幅（lookback 模式）

```jsonc
"pairlists": [
    {
        "method": "GainersLosersPairList",
        "gainers_count": 5,
        "losers_count": 5,
        "direction": "both",
        "mode": "union",
        "lookback_period": 7,
        "lookback_timeframe": "1d",
        "refresh_period": 86400    // 每日刷新（1d 数据）
    }
]
```

---

## 五、如何验证配置

```bash
# 在 Docker 内测试交易对生成
docker compose run --rm CK_Quant test-pairlist \
    --userdir /CK_Quant/user_data \
    --config /CK_Quant/user_data/config.json
```

输出示例（union 模式 14 对）：
```
Pairs for USDT:
['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SNDK/USDT:USDT', 'SPCX/USDT:USDT', 'XAU/USDT:USDT',
 'GPS/USDT:USDT', 'TUT/USDT:USDT', 'STAR/USDT:USDT', 'HEMI/USDT:USDT', 'ACE/USDT:USDT',
 'VELVET/USDT:USDT', 'CYS/USDT:USDT', 'BEAT/USDT:USDT', 'SOL/USDT:USDT']
# 前 5 = 成交额榜，中 5 = 涨幅榜，后 3 = 跌幅榜，SOL = 静态新增
```

---

## 六、注意事项

1. **需要交易所支持 tickers 涨跌幅数据**：Binance 等主流交易所默认支持（`tickers_have_percentage`）
2. **refresh_period**：24h ticker 模式建议 ≥ 1800 秒（30 分钟），避免频繁请求被限流
3. **lookback 模式**：`refresh_period` 必须 ≥ 一个回看周期的秒数（如 1d K线 → ≥ 86400）
4. **与回测**：`supports_backtesting = NO`（涨跌幅排名需要实时 ticker，**不支持回测**）—— 回测时请用静态白名单
5. **隐私**：这是框架能力，不含任何策略逻辑，可放心公开使用
