# CK Quant

**隐私优先、支持网页与 Android 远程管理的 Freqtrade 二次发行版**<br>
**A privacy-first Freqtrade distribution with Web and Android remote management**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## 特性 | Features

| 中文 | English |
|---|---|
| 崩溃安全的订单恢复（应对快速反手交易） | crash-safe exchange-order recovery for rapid stop-and-reverse trading |
| 可选合成冰山单（入场/出场拆分隐藏意图） | optional synthetic iceberg execution for entries and regular exits |
| 响应式半透明卡片式 CK Quant UI | a responsive, translucent card-based CK Quant UI |
| WebUI 支持简体中文、繁体中文、英语、德语、日语、法语和韩语 | WebUI localization for Simplified Chinese, Traditional Chinese, English, German, Japanese, French, and Korean |
| 经鉴权的配置与策略在线编辑、校验、自动备份及重载 | authenticated config/strategy editing with validation, automatic backups, and reload |
| Android App 登录量化服务器、管理机器人及操作订单 | Android app for connecting to a CK Quant server, managing bots, and operating trades |
| 可复现的 CPU / FreqAI Docker 镜像 | reproducible CPU and FreqAI Docker image definitions |
| **Tick 级回测引擎**（真实逐笔撮合，内存友好） | a memory-friendly **tick-level backtest engine** matching exits on real tick sequences instead of guessing OHLCV bar paths |
| **精确回撤百分比**（钱包余额含未平仓浮盈） | accurate drawdown: backtest wallet balance includes unrealized P&L of open positions (true account equity) |

> **策略保密**：真实策略、配置、模型、数据库、日志、凭据和服务器信息
> **有意不包含**在本仓库中。
> **Strategy privacy**：Real strategies, configurations, models, databases,
> logs, credentials, and server details are intentionally **not** part of
> this repository. See [CK_QUANT.md](CK_QUANT.md) for architecture notes.

本项目源自 Freqtrade，保持 GPL-3.0 许可。上游项目、归属、文档和安全声明见下文。
This project is derived from Freqtrade and remains GPL-3.0 licensed. The
upstream project, attribution, documentation, and safety notice follow below.

---

## 多语言 WebUI 与 Android App | Multilingual WebUI & Android app

CK Quant WebUI 现在提供七种语言，并新增管理员页面，可在浏览器或 Android App 中：

交易、仪表盘和图表工作区的卡片标题、表格字段、图例、操作按钮、确认弹窗与空状态均会随所选语言切换。

- 修改常用或完整配置参数，并在保存前进行服务端校验；
- 修改策略参数或在线编辑策略文件；
- 自动创建配置/策略备份，保存后安全重载或重启机器人；
- 查看运行状态，并通过原有 Freqtrade API 管理订单和持仓；
- 查看管理员操作审计记录。

CK Quant WebUI now supports seven languages. Its authenticated admin workspace can
localize the complete trading, dashboard, and chart surfaces, including card titles,
table fields, legends, actions, confirmation dialogs, and empty states. It can also
edit and validate configuration or strategy files, create automatic backups, apply
changes, manage the bot and trades through the existing Freqtrade API, and retain an
administrative audit trail.

The dashboard now combines bot comparison, the essential `/profit` metrics, and
the cumulative-profit chart in one responsive overview card. Desktop screens use
a readable side-by-side layout, while portrait phones stack the smooth profit
curve below the bot statistics. Larger metric typography and a clear vertical
scale make profit quality and drawdown easier to assess at a glance.

管理员功能默认关闭。先在 `config.json` 中显式启用所需权限：

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

Android APK 可从 [GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest)
下载。安装后输入服务器地址以及 `api_server` 用户名和密码即可连接。
完整配置、反向代理和安全说明见
[移动管理指南](docs/ck_quant_mobile_admin.md)。

> **安全提示 / Security:** 不要将管理端口裸露到公网。远程使用时请配置
> HTTPS 反向代理或可信 VPN，并使用高强度独立密码和 JWT 密钥。建议先连接
> `dry_run` 实例完成验证。

---

## Docker 快速开始 | Docker quick start

推荐镜像：`ericchenghz/ck-quant:stable`。新部署默认使用目录名 `CK_Quant`：

```bash
mkdir CK_Quant
cd CK_Quant

curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml

docker compose pull
docker compose run --rm ck-quant create-userdir --userdir user_data
docker compose run --rm ck-quant new-config --config user_data/config.json
```

> 源码仓库公开后，任何人都可从 GitHub 下载该文件；Docker Hub 镜像无需登录即可拉取。
> The raw GitHub URL is publicly downloadable once this repository is public.
> The Docker Hub image is already public and can be pulled without signing in.

把你的策略放入 `user_data/strategies/`，下载 `.env.example` 为 `.env`，
并将 `CK_QUANT_STRATEGY` 设为策略类名，然后启动：

```bash
docker compose up -d
docker compose logs -f --tail 200
```

WebUI 默认监听 <http://127.0.0.1:8080>。配置、策略、数据库、凭据、模型和
日志都保存在本地 `user_data` 目录，不进入镜像。

更多信息见 [CK Quant Docker 快速开始](docs/ck-quant-docker.md)（环境变量、
镜像标签、安全指南、常用命令）。

---

## Tick 级回测引擎 | Tick-level backtest

用真实逐笔成交（tick）撮合出场，解决 OHLCV 回测的精度问题：

```text
同一根 15m bar 内，止损和止盈都被触及 —— 谁先谁后？
  OHLCV 回测：只能猜（假设路径）→ 系统性偏向乐观 ❌
  Tick 回测：真实 tick 序列逐笔判断 → 精确 ✅
```

**实测**（ETH 2025-07，0.5% 止损）：7.1% 的交易触发顺序判断错误，
且 OHLCV 总盈亏方向与真实 tick 相反。止损越紧误差越大。

```bash
# 下载 tick 数据（binance.vision，按周分块）
python scripts/download_vision_chunked.py ETHUSDT 20250701 20250731 \
    user_data/data/binance/futures/trades_eth

# 运行 tick 回测
python -m freqtrade.ck_quant.tick_backtest \
    --config user_data/config.json --strategy CK_Trend \
    --data-dir user_data/data/binance/futures/trades_eth \
    --timerange 20250701-20250731 --pair "ETH/USDT:USDT" \
    --stoploss 0.005 --takeprofit 0.005
```

详见 [docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md)。

---

## 合成冰山单 | Synthetic Iceberg Orders

把一笔大订单拆成多个小子单，交易所同一时刻只看到一个，前一片成交后再补：

```json
{
    "iceberg_orders": {
        "enabled": true,
        "entry": true,
        "exit": true,
        "visible_ratio": 0.1,
        "max_slices": 10,
        "replenish_interval": 5.0,
        "size_jitter": 0.0
    }
}
```

详见 [docs/advanced-iceberg.md](docs/advanced-iceberg.md)。

---

## 一键发布 | One-command release

```bash
python scripts/release.py 2026.8          # 构建镜像 → 推送 Docker Hub → 打 tag → 创建 Release
python scripts/release.py 2026.8 --dry-run  # 预览
```

---

## Freqtrade upstream

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade is a free and open source crypto trading bot written in Python. It is designed to support all major exchanges and be controlled via Telegram or webUI. It contains backtesting, plotting and money management tools as well as strategy optimization by machine learning.

![freqtrade](https://raw.githubusercontent.com/freqtrade/freqtrade/develop/docs/assets/freqtrade-screenshot.png)
## Disclaimer

This software is for educational purposes only. Do not risk money which
you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS
AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.

Always start by running a trading bot in Dry-Run and do not engage money
before you understand how it works and what profit/loss you should
expect.

We strongly recommend you to have coding and Python knowledge. Do not
hesitate to read the source code and understand the mechanism of this bot.

## Supported Exchange marketplaces

Please read the [exchange-specific notes](https://www.freqtrade.io/en/stable/exchanges/) to learn about special configurations that maybe needed for each exchange.

### Supported Spot Exchanges

- [X] [Binance](https://www.binance.com/)
- [X] [BingX](https://bingx.com/invite/0EM9RX)
- [X] [Bitget](https://www.bitget.com/)
- [X] [Bitmart](https://bitmart.com/)
- [X] [Bybit EU](https://bybit.eu/)
- [X] [Bybit](https://bybit.com/)
- [X] [Gate EU](https://www.gate.com/en-eu)
- [X] [Gate](https://www.gate.com/ref/6266643)
- [X] [HTX](https://www.htx.com/)
- [X] [Hyperliquid](https://hyperliquid.xyz/) (A decentralized exchange, or DEX)
- [X] [Kraken](https://kraken.com/)
- [X] [MyOKX](https://okx.com/) (OKX EEA)
- [X] [OKX](https://okx.com/)
- [ ] [potentially many others](https://github.com/ccxt/ccxt/). _(We cannot guarantee they will work)_

### Supported Futures Exchanges

- [X] [Binance](https://www.binance.com/)
- [X] [Bitget](https://www.bitget.com/)
- [X] [Bybit](https://bybit.com/)
- [X] [Gate](https://www.gate.com/ref/6266643)
- [X] [Hyperliquid](https://hyperliquid.xyz/) (A decentralized exchange, or DEX)
- [X] [Kraken](https://www.kraken.com/features/futures)
- [X] [OKX](https://okx.com/)

Please make sure to read the [exchange specific notes](https://www.freqtrade.io/en/stable/exchanges/), as well as the [trading with leverage](https://www.freqtrade.io/en/stable/leverage/) documentation before diving in.

### Community tested

Exchanges confirmed working by the community:

- [X] [Bitvavo](https://bitvavo.com/)
- [X] [Kucoin](https://www.kucoin.com/)

## Documentation

We invite you to read the bot documentation to ensure you understand how the bot is working.

Please find the complete documentation on the [freqtrade website](https://www.freqtrade.io).

## Features

- [x] **Based on Python 3.11+**: For botting on any operating system - Windows, macOS and Linux.
- [x] **Persistence**: Persistence is achieved through sqlite.
- [x] **Dry-run**: Run the bot without paying money.
- [x] **Backtesting**: Run a simulation of your buy/sell strategy.
- [x] **Strategy Optimization by machine learning**: Use machine learning to optimize your buy/sell strategy parameters with real exchange data.
- [X] **Adaptive prediction modeling**: Build a smart strategy with FreqAI that self-trains to the market via adaptive machine learning methods. [Learn more](https://www.freqtrade.io/en/stable/freqai/)
- [x] **Whitelist crypto-currencies**: Select which crypto-currency you want to trade or use dynamic whitelists.
- [x] **Blacklist crypto-currencies**: Select which crypto-currency you want to avoid.
- [x] **Builtin WebUI**: Builtin web UI to manage your bot.
- [x] **Manageable via Telegram**: Manage the bot with Telegram.
- [x] **Display profit/loss in fiat**: Display your profit/loss in fiat currency.
- [x] **Performance status report**: Provide a performance status of your current trades.

## Quick start

Please refer to the [Docker Quickstart documentation](https://www.freqtrade.io/en/stable/docker_quickstart/) on how to get started quickly.

For further (native) installation methods, please refer to the [Installation documentation page](https://www.freqtrade.io/en/stable/installation/).

## Basic Usage

### Bot commands

```
usage: freqtrade [-h] [-V]
                 {trade,create-userdir,new-config,show-config,new-strategy,download-data,convert-data,convert-trade-data,trades-to-ohlcv,list-data,backtesting,backtesting-show,backtesting-analysis,edge,hyperopt,hyperopt-list,hyperopt-show,list-exchanges,list-markets,list-pairs,list-strategies,list-hyperoptloss,list-freqaimodels,list-timeframes,show-trades,test-pairlist,convert-db,install-ui,plot-dataframe,plot-profit,webserver,strategy-updater,lookahead-analysis,recursive-analysis}
                 ...

Free, open source crypto trading bot

positional arguments:
  {trade,create-userdir,new-config,show-config,new-strategy,download-data,convert-data,convert-trade-data,trades-to-ohlcv,list-data,backtesting,backtesting-show,backtesting-analysis,edge,hyperopt,hyperopt-list,hyperopt-show,list-exchanges,list-markets,list-pairs,list-strategies,list-hyperoptloss,list-freqaimodels,list-timeframes,show-trades,test-pairlist,convert-db,install-ui,plot-dataframe,plot-profit,webserver,strategy-updater,lookahead-analysis,recursive-analysis}
    trade               Trade module.
    create-userdir      Create user-data directory.
    new-config          Create new config
    show-config         Show resolved config
    new-strategy        Create new strategy
    download-data       Download backtesting data.
    convert-data        Convert candle (OHLCV) data from one format to
                        another.
    convert-trade-data  Convert trade data from one format to another.
    trades-to-ohlcv     Convert trade data to OHLCV data.
    list-data           List downloaded data.
    backtesting         Backtesting module.
    backtesting-show    Show past Backtest results
    backtesting-analysis
                        Backtest Analysis module.
    hyperopt            Hyperopt module.
    hyperopt-list       List Hyperopt results
    hyperopt-show       Show details of Hyperopt results
    list-exchanges      Print available exchanges.
    list-markets        Print markets on exchange.
    list-pairs          Print pairs on exchange.
    list-strategies     Print available strategies.
    list-hyperoptloss   Print available hyperopt loss functions.
    list-freqaimodels   Print available freqAI models.
    list-timeframes     Print available timeframes for the exchange.
    show-trades         Show trades.
    test-pairlist       Test your pairlist configuration.
    convert-db          Migrate database to different system
    install-ui          Install FreqUI
    plot-dataframe      Plot candles with indicators.
    plot-profit         Generate plot showing profits.
    webserver           Webserver module.
    strategy-updater    updates outdated strategy files to the current version
    lookahead-analysis  Check for potential look ahead bias.
    recursive-analysis  Check for potential recursive formula issue.

options:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit
```

### Telegram RPC commands

Telegram is not mandatory. However, this is a great way to control your bot. More details and the full command list on the [documentation](https://www.freqtrade.io/en/stable/telegram-usage/)

- `/start`: Starts the trader.
- `/stop`: Stops the trader.
- `/stopentry`: Stop entering new trades.
- `/status <trade_id>|[table]`: Lists all or specific open trades.
- `/profit [<n>]`: Lists cumulative profit from all finished trades, over the last n days.
- `/profit_long [<n>]`: Lists cumulative profit from all finished long trades, over the last n days.
- `/profit_short [<n>]`: Lists cumulative profit from all finished short trades, over the last n days.
- `/forceexit <trade_id>|all`: Instantly exits the given trade (Ignoring `minimum_roi`).
- `/fx <trade_id>|all`: Alias to `/forceexit`
- `/performance`: Show performance of each finished trade grouped by pair
- `/balance`: Show account balance per currency.
- `/daily <n>`: Shows profit or loss per day, over the last n days.
- `/help`: Show help message.
- `/version`: Show version.


## Development branches

The project is currently setup in two main branches:

- `develop` - This branch has often new features, but might also contain breaking changes. We try hard to keep this branch as stable as possible.
- `stable` - This branch contains the latest stable release. This branch is generally well tested.
- `feat/*` - These are feature branches, which are being worked on heavily. Please don't use these unless you want to test a specific feature.

## Support

### Help / Discord

For any questions not covered by the documentation or for further information about the bot, or to simply engage with like-minded individuals, we encourage you to join the Freqtrade [discord server](https://discord.gg/p7nuUNVfP7).

### [Bugs / Issues](https://github.com/freqtrade/freqtrade/issues?q=is%3Aissue)

If you discover a bug in the bot, please
[search the issue tracker](https://github.com/freqtrade/freqtrade/issues?q=is%3Aissue)
first. If it hasn't been reported, please
[create a new issue](https://github.com/freqtrade/freqtrade/issues/new/choose) and
ensure you follow the template guide so that the team can assist you as
quickly as possible.

For every [issue](https://github.com/freqtrade/freqtrade/issues/new/choose) created, kindly follow up and mark satisfaction or reminder to close issue when equilibrium ground is reached.

--Maintain github's [community policy](https://docs.github.com/en/site-policy/github-terms/github-community-code-of-conduct)--

### [Feature Requests](https://github.com/freqtrade/freqtrade/labels/enhancement)

Have you a great idea to improve the bot you want to share? Please,
first search if this feature was not [already discussed](https://github.com/freqtrade/freqtrade/labels/enhancement).
If it hasn't been requested, please
[create a new request](https://github.com/freqtrade/freqtrade/issues/new/choose)
and ensure you follow the template guide so that it does not get lost
in the bug reports.

### [Pull Requests](https://github.com/freqtrade/freqtrade/pulls)

Feel like the bot is missing a feature? We welcome your pull requests!

Please read the
[Contributing document](https://github.com/freqtrade/freqtrade/blob/develop/CONTRIBUTING.md)
to understand the requirements before sending your pull-requests.

Coding is not a necessity to contribute - maybe start with improving the documentation?
Issues labeled [good first issue](https://github.com/freqtrade/freqtrade/labels/good%20first%20issue) can be good first contributions, and will help get you familiar with the codebase.

**Note** before starting any major new feature work, *please open an issue describing what you are planning to do* or talk to us on [discord](https://discord.gg/p7nuUNVfP7) (please use the #dev channel for this). This will ensure that interested parties can give valuable feedback on the feature, and let others know that you are working on it.

**Important:** Always create your PR against the `develop` branch, not `stable`.

## Requirements

### Up-to-date clock

The clock must be accurate, synchronized to a NTP server very frequently to avoid problems with communication to the exchanges.

### Minimum hardware required

To run this bot we recommend you a cloud instance with a minimum of:

- Minimal (advised) system requirements: 2GB RAM, 1GB disk space, 2vCPU

### Software requirements

- [Python >= 3.11](http://docs.python-guide.org/en/latest/starting/installation/)
- [pip](https://pip.pypa.io/en/stable/installing/)
- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- [TA-Lib](https://ta-lib.github.io/ta-lib-python/)
- [virtualenv](https://virtualenv.pypa.io/en/stable/installation.html) (Recommended)
- [Docker](https://www.docker.com/products/docker) (Recommended)
