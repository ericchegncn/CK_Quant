# CK Quant 详细部署与使用教程

> 本教程适用于 CK Quant 的本地模拟盘、Linux 服务器实盘、WebUI、Telegram、
> 合成冰山单以及 FreqAI/FreqAI-RL。命令中的账号、密钥、IP、策略名和路径均为
> 示例，请替换为自己的值。

## 1. CK Quant 是什么

CK Quant 是基于 Freqtrade 二次开发的量化交易系统，目前包含以下核心改动：

1. 修复快速平仓并立即反向开仓时，旧止损成交单可能被错误关联到新交易的问题。
2. 在订单恢复发生异常时主动回滚数据库事务，避免容器进入无限重启循环。
3. 支持合成冰山单：每次只向交易所展示一个子单，成交后再提交下一子单。
4. 内置 CK Quant WebUI，使用半透明卡片式界面。
5. 提供普通、FreqAI 和 FreqAI-RL 三类 Docker 镜像构建方式。

CK Quant 仍然保留 Freqtrade 的命令、策略接口、数据库结构和大部分配置方式，因此
原有 Freqtrade 策略通常可以直接使用。

### 1.1 CK Quant 修复的边界

订单恢复补丁主要包含三层保护：

- 恢复订单不得早于当前交易的第一笔入场订单；
- 如果同一交易对下的订单 ID 已属于其他交易，则不得再次导入；
- 订单恢复异常后回滚 SQLAlchemy 会话，避免 `PendingRollbackError` 导致循环崩溃。

该修复用于防止新的错误关联，不会自动修复已经损坏的旧数据库记录，也不会把手动
交易所订单自动导入 Freqtrade。

## 2. 隐私和安全原则

CK Quant 源代码仓库与实际运行数据必须分离。

不得上传到 GitHub 的内容包括：

- 交易所 API Key、Secret；
- Telegram Token、Chat ID；
- WebUI 密码、JWT 密钥和 WebSocket Token；
- 私有策略；
- 实盘配置文件；
- SQLite 数据库及其 `-wal`、`-shm` 文件；
- 日志、模型、回测结果和服务器信息。

项目的 `.gitignore` 已忽略常见运行文件，但提交前仍应检查：

```powershell
cd "D:\Eric Cheng\Documents\CK_Quant"
git status --short
```

不要习惯性执行 `git add .`。应只添加明确需要公开的源代码或文档，例如：

```powershell
git add README.md CK_Quant部署与使用教程.md
```

运行配置最好放在独立目录，通过 Docker bind mount 挂载到容器。例如：

- Windows：`D:\CKQuantRuntime\user_data`
- Linux：`/opt/ck-quant/user_data`

## 3. 镜像类型

CK Quant 提供三种镜像：

| 用途 | 推荐标签 | 内容 |
|---|---|---|
| 普通策略 | `ck-quant:local` | CK Quant、WebUI、冰山单、订单恢复修复 |
| FreqAI | `ck-quant:freqai` | 普通镜像加 FreqAI 依赖 |
| FreqAI-RL | `ck-quant:freqai-rl` | FreqAI 镜像加强化学习依赖 |

普通策略不要使用 FreqAI 镜像，以免浪费磁盘空间和启动时间。

## 4. Windows 本地构建

### 4.1 前置条件

需要安装：

- Git；
- Docker Desktop；
- WSL2 后端；
- 至少约 10 GB 可用磁盘空间；FreqAI-RL 建议预留更多空间。

确认 Docker 正常：

```powershell
docker version
docker compose version
```

### 4.2 构建普通镜像

```powershell
cd "D:\Eric Cheng\Documents\CK_Quant"
docker build -t ck-quant:local .
```

确认镜像：

```powershell
docker image inspect ck-quant:local
docker run --rm ck-quant:local --version
```

### 4.3 构建 FreqAI 镜像

```powershell
cd "D:\Eric Cheng\Documents\CK_Quant"

docker build `
  -f docker/Dockerfile.ck-quant-freqai `
  --build-arg sourceimage=ck-quant `
  --build-arg sourcetag=local `
  -t ck-quant:freqai .
```

### 4.4 构建 FreqAI-RL 镜像

必须先完成普通镜像和 FreqAI 镜像的构建：

```powershell
cd "D:\Eric Cheng\Documents\CK_Quant"

docker build `
  -f docker/Dockerfile.ck-quant-freqai-rl `
  --build-arg sourceimage=ck-quant `
  --build-arg sourcetag=freqai `
  -t ck-quant:freqai-rl .
```

### 4.5 使用版本标签

不要只保留 `local` 标签。每次确认可用后增加日期或版本标签，便于回滚：

```powershell
docker tag ck-quant:local ck-quant:2026.07.30
```

## 5. 准备运行目录

以 Windows 为例：

```powershell
$runtimeRoot = "D:\CKQuantRuntime"

New-Item -ItemType Directory -Force -Path "$runtimeRoot\user_data\strategies"
New-Item -ItemType Directory -Force -Path "$runtimeRoot\user_data\logs"
New-Item -ItemType Directory -Force -Path "$runtimeRoot\user_data\models"
New-Item -ItemType Directory -Force -Path "$runtimeRoot\user_data\freqaimodels"
```

复制自己的策略和配置：

```powershell
Copy-Item `
  "D:\你的私有目录\YourStrategy.py" `
  "$runtimeRoot\user_data\strategies\YourStrategy.py"

Copy-Item `
  "D:\你的私有目录\config.dryrun.json" `
  "$runtimeRoot\user_data\config.dryrun.json"
```

建议为模拟盘和实盘分别使用不同文件：

```text
user_data/
├── config.dryrun.json
├── config.live.json
├── strategies/
│   └── YourStrategy.py
├── logs/
├── models/
└── freqaimodels/
```

模拟盘和实盘还必须使用不同的数据库、日志、Bot 名称和 Telegram Bot。

## 6. 基础配置

下面仅展示关键结构，不要直接用于实盘：

```json
{
  "max_open_trades": 10,
  "stake_currency": "USDT",
  "stake_amount": 20,
  "tradable_balance_ratio": 0.99,
  "dry_run": true,
  "dry_run_wallet": 10000,
  "trading_mode": "futures",
  "margin_mode": "cross",
  "exchange": {
    "name": "binance",
    "key": "YOUR_EXCHANGE_KEY",
    "secret": "YOUR_EXCHANGE_SECRET",
    "pair_whitelist": [
      "BTC/USDT:USDT",
      "ETH/USDT:USDT"
    ],
    "pair_blacklist": []
  },
  "pairlists": [
    {
      "method": "StaticPairList"
    }
  ],
  "telegram": {
    "enabled": false,
    "token": "YOUR_TELEGRAM_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "api_server": {
    "enabled": true,
    "listen_ip_address": "0.0.0.0",
    "listen_port": 8080,
    "verbosity": "error",
    "enable_openapi": false,
    "jwt_secret_key": "GENERATE_A_LONG_RANDOM_VALUE",
    "ws_token": "GENERATE_ANOTHER_LONG_RANDOM_VALUE",
    "CORS_origins": [],
    "username": "YOUR_WEBUI_USER",
    "password": "YOUR_STRONG_WEBUI_PASSWORD"
  },
  "bot_name": "CK Quant Dryrun",
  "initial_state": "running",
  "force_entry_enable": false,
  "internals": {
    "process_throttle_secs": 5
  }
}
```

注意：

- 模拟盘必须保持 `"dry_run": true`。
- 实盘必须使用只允许读取和交易、禁止提现的 API Key。
- 交易所 API 应设置服务器 IP 白名单。
- `trading_mode`、`margin_mode` 和交易对格式必须与策略及交易所账户一致。
- 合约交易对通常使用 `BTC/USDT:USDT` 格式。
- 不要让两个机器人使用同一个 Telegram Token 轮询消息。

## 7. Docker Compose 配置

在运行目录创建 `docker-compose.yml`。Windows 示例：

```yaml
services:
  ck-quant:
    image: ck-quant:local
    container_name: ck-quant-dryrun
    restart: unless-stopped
    volumes:
      - "D:/CKQuantRuntime/user_data:/freqtrade/user_data"
    ports:
      - "127.0.0.1:8080:8080"
    command:
      - trade
      - --logfile
      - /freqtrade/user_data/logs/ck-quant-dryrun.log
      - --db-url
      - sqlite:////freqtrade/user_data/tradesv3-ck-quant-dryrun.sqlite
      - --config
      - /freqtrade/user_data/config.dryrun.json
      - --strategy
      - YourStrategy
```

先验证 Compose：

```powershell
cd "D:\CKQuantRuntime"
docker compose config
```

启动：

```powershell
docker compose up -d
```

检查：

```powershell
docker compose ps
docker inspect ck-quant-dryrun --format "{{json .State}}"
docker logs --tail 200 ck-quant-dryrun
```

停止：

```powershell
docker compose stop
```

停止并移除容器但保留挂载数据：

```powershell
docker compose down
```

`down` 不会删除 bind mount 中的 `user_data`，但不要添加 `-v`，除非明确知道要
删除什么。

## 8. 启动前验证

### 8.1 检查配置解析

```powershell
docker run --rm `
  -v "D:/CKQuantRuntime/user_data:/freqtrade/user_data" `
  ck-quant:local `
  show-config `
  --config /freqtrade/user_data/config.dryrun.json
```

输出可能隐藏部分密钥，但仍不要把完整输出发布到公开平台。

### 8.2 检查策略加载

```powershell
docker run --rm `
  -v "D:/CKQuantRuntime/user_data:/freqtrade/user_data" `
  ck-quant:local `
  list-strategies `
  --userdir /freqtrade/user_data `
  --config /freqtrade/user_data/config.dryrun.json
```

确认策略状态为可加载，且没有 Python 导入错误。

### 8.3 检查交易对

```powershell
docker run --rm `
  -v "D:/CKQuantRuntime/user_data:/freqtrade/user_data" `
  ck-quant:local `
  test-pairlist `
  --config /freqtrade/user_data/config.dryrun.json
```

### 8.4 确认没有重复实例

```powershell
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

同一配置、数据库、Telegram Token 或交易账户不能由两个实例同时管理。

## 9. 访问 CK Quant WebUI

本地 Compose 把端口绑定到：

```text
http://127.0.0.1:8080
```

使用配置中 `api_server.username` 和 `api_server.password` 登录。

如果页面无法访问，依次检查：

```powershell
docker compose ps
docker logs --tail 200 ck-quant-dryrun
Test-NetConnection 127.0.0.1 -Port 8080
```

如果能访问 API 但仍显示旧界面：

1. 强制刷新浏览器；
2. 清理该站点缓存；
3. 确认容器使用的是 `ck-quant:*`，而不是官方 Freqtrade 镜像；
4. 重新构建镜像时不要复用错误的旧标签。

## 10. 启用合成冰山单

### 10.1 工作方式

CK Quant 使用合成冰山单，而不是依赖交易所原生 `icebergQty`：

1. 本地数据库保存完整目标仓位；
2. 交易所一次只看到一个子单；
3. 当前子单完成后，等待设定间隔；
4. 再提交下一子单，直到完成目标仓位。

一个交易计划在 Freqtrade 中仍算一笔 Trade，不会因为拆成十份而占用十个
`max_open_trades` 名额。

### 10.2 配置

在实际运行配置的顶层加入：

```json
"iceberg_orders": {
  "enabled": true,
  "entry": true,
  "exit": false,
  "visible_ratio": 0.1,
  "max_slices": 10,
  "min_slice_stake": 5,
  "replenish_interval": 5,
  "size_jitter": 0.15
}
```

参数说明：

| 参数 | 说明 |
|---|---|
| `enabled` | 冰山单总开关，默认关闭 |
| `entry` | 是否拆分普通入场订单 |
| `exit` | 是否拆分普通信号退出和 `custom_exit` |
| `visible_ratio` | 单个子单占总目标的基础比例 |
| `max_slices` | 最大拆分数量，允许范围 2～100 |
| `min_slice_stake` | 单个子单最低保证金金额 |
| `replenish_interval` | 前一子单完成后到下一子单的最短间隔，单位为秒 |
| `size_jitter` | 在基础子单上增加随机变化，允许范围 0～0.5 |

实际基础子单保证金为：

```text
max(
    总保证金 × visible_ratio,
    总保证金 ÷ max_slices,
    min_slice_stake
)
```

如果启用 `size_jitter`，子单只会在这个基础上随机增大，不会因此超过剩余目标。

### 10.3 CK_Trend 推荐设置

对需要在趋势反转时快速平仓并立即反向开仓的策略，建议：

```json
"entry": true,
"exit": false
```

原因是 `exit: true` 会拆分普通退出信号和 `custom_exit`。这可能延迟完成平仓，进而
延迟反向开仓。入场使用冰山、退出一次性完成，更符合快速止损和快速反向的策略逻辑。

以下退出类型始终绕过冰山，不会被拆分：

- 止损；
- 移动止损；
- 强平；
- 紧急退出；
- 强制退出。

### 10.4 设置最低子单

`min_slice_stake` 不能机械照抄。

例如总保证金只有 50 USDT：

- 设置为 5 USDT，理论上可拆约 10 份；
- 设置为 25 USDT，最多只能拆约 2 份。

同时还要考虑杠杆、交易所最低名义价值、数量精度和最小下单量。首次启用应在
模拟盘中观察是否出现 `min notional`、`amount` 或 `precision` 错误。

### 10.5 启用和验证

修改配置后重启同一个容器：

```powershell
docker compose restart ck-quant
```

日志中出现以下内容代表入场拆分生效：

```text
CK Quant iceberg entry for ...
```

如果开启退出冰山，还会看到：

```text
CK Quant iceberg exit for ...
```

冰山配置只影响之后触发的订单。它不会把已经完全建立的旧仓位重新拆分入场；如果
启用了退出冰山，旧持仓之后收到普通退出信号时仍可能被拆分退出。

## 11. Telegram

配置示例：

```json
"telegram": {
  "enabled": true,
  "token": "YOUR_UNIQUE_BOT_TOKEN",
  "chat_id": "YOUR_CHAT_ID"
}
```

常用命令：

| 命令 | 用途 |
|---|---|
| `/start` | 启动交易 |
| `/stop` | 停止交易逻辑 |
| `/stopentry` | 停止新开仓，继续管理已有仓位 |
| `/status table` | 查看机器人数据库中的持仓 |
| `/profit` | 查看已平仓收益 |
| `/performance` | 按交易对统计 |
| `/balance` | 查看余额 |
| `/version` | 查看版本 |

Telegram 能收到通知但命令没有响应时：

1. 确认同一个 Token 没有被其他机器人或容器使用；
2. 查看是否存在 `getUpdates` conflict；
3. 确认 Chat ID 在允许范围内；
4. 检查容器到 Telegram API 的网络；
5. 只重启当前机器人，不要启动第二个副本。

## 12. Linux 服务器部署

### 12.1 准备目录

```bash
sudo install -d -m 750 -o "$USER" -g "$USER" /opt/ck-quant
install -d -m 750 /opt/ck-quant/user_data/strategies
install -d -m 750 /opt/ck-quant/user_data/logs
install -d -m 750 /opt/ck-quant/user_data/models
install -d -m 750 /opt/ck-quant/user_data/freqaimodels
```

检查系统时间：

```bash
timedatectl status
```

服务器时间必须保持同步，否则交易所签名请求可能失败。

### 12.2 方式一：在服务器构建

在有权访问私有仓库的前提下：

```bash
git clone YOUR_PRIVATE_REPOSITORY_URL /opt/ck-quant/source
cd /opt/ck-quant/source
docker build -t ck-quant:2026.07.30 .
```

不要把运行数据复制进源代码目录，也不要把实盘配置提交到仓库。

### 12.3 方式二：从本地导出镜像

Windows 导出：

```powershell
docker save ck-quant:local -o "D:\CKQuantImages\ck-quant-2026.07.30.tar"
```

复制到服务器：

```powershell
scp "D:\CKQuantImages\ck-quant-2026.07.30.tar" USER@SERVER:/opt/ck-quant/
```

服务器导入：

```bash
docker load -i /opt/ck-quant/ck-quant-2026.07.30.tar
docker image ls ck-quant
```

如有需要，增加服务器使用的标签：

```bash
docker tag ck-quant:local ck-quant:2026.07.30
```

镜像不包含运行配置、私有策略、数据库和密钥，这些文件必须单独安全传输。

### 12.4 Linux Compose 示例

在 `/opt/ck-quant/docker-compose.yml` 中写入：

```yaml
services:
  ck-quant:
    image: ck-quant:2026.07.30
    container_name: ck-quant-live
    restart: unless-stopped
    volumes:
      - "/opt/ck-quant/user_data:/freqtrade/user_data"
    ports:
      - "127.0.0.1:8080:8080"
    command:
      - trade
      - --logfile
      - /freqtrade/user_data/logs/ck-quant-live.log
      - --db-url
      - sqlite:////freqtrade/user_data/tradesv3-ck-quant-live.sqlite
      - --config
      - /freqtrade/user_data/config.live.json
      - --strategy
      - YourStrategy
```

启动：

```bash
cd /opt/ck-quant
docker compose config
docker compose up -d
docker compose ps
docker logs --tail 200 ck-quant-live
```

### 12.5 安全访问远程 WebUI

推荐只监听服务器的 `127.0.0.1`，通过 SSH 隧道访问：

```powershell
ssh -L 8080:127.0.0.1:8080 USER@SERVER
```

然后在本机打开：

```text
http://127.0.0.1:8080
```

不建议直接把 8080 端口暴露到公网。如果必须公开，应使用 HTTPS 反向代理、防火墙
白名单和强密码。

## 13. 从官方 Freqtrade 镜像迁移到 CK Quant

迁移实盘时，最重要的是保留数据库并确保只有一个实例管理账户。

### 13.1 迁移前

1. 记录旧容器名、镜像、配置、策略、数据库和挂载路径；
2. 在交易所记录当前持仓、方向、数量和止损订单；
3. 使用 `/stopentry` 暂停新入场；
4. 确认没有正在提交或撤销的订单；
5. 停止旧容器；
6. 停止后再备份数据库。

示例：

```bash
docker stop OLD_BOT_CONTAINER
mkdir -p /opt/ck-quant/backups/pre-migration-YYYYMMDD-HHMMSS
cp -a /path/to/old/user_data/. \
  /opt/ck-quant/backups/pre-migration-YYYYMMDD-HHMMSS/
```

SQLite 使用 WAL 模式时，不能在机器人仍写入数据库时只复制主 `.sqlite` 文件。应先
停止机器人，再复制 `.sqlite`、`.sqlite-wal` 和 `.sqlite-shm`，或使用 SQLite
备份命令：

```bash
sqlite3 /path/to/trades.sqlite \
  ".backup /opt/ck-quant/backups/trades-backup.sqlite"
```

### 13.2 启动 CK Quant

CK Quant 应继续挂载原来的策略、配置和数据库，命令中的 `--db-url` 必须指向正确
数据库：

```text
sqlite:////freqtrade/user_data/tradesv3.sqlite
```

启动前确认：

- `dry_run` 没有被意外改变；
- 策略名称完全相同；
- 交易模式、保证金模式和交易所相同；
- 数据库路径正确；
- 原容器已经停止；
- 新容器没有使用另一个空数据库。

### 13.3 迁移后核验

同时检查：

1. Freqtrade `/status table` 中的开放交易；
2. 交易所实际持仓；
3. 每个持仓的方向和数量；
4. 每个持仓对应的交易所止损数量；
5. 数据库是否存在交易所已经关闭的幽灵持仓；
6. 容器 `RestartCount` 是否保持为 0。

检查容器：

```bash
docker inspect ck-quant-live \
  --format 'status={{.State.Status}} restart={{.RestartCount}} oom={{.State.OOMKilled}}'
```

### 13.4 手动交易的处理

Freqtrade 不会自动接管手动建立的交易所仓位。手动仓位可能存在于交易所，却不会出现
在 `/status table`；这与数据库幽灵订单是两个不同问题。

除非明确计划由机器人接管，否则不要手工把该仓位写进数据库，也不要让机器人替它
创建止损。应在交易所中单独管理手动仓位。

## 14. 从模拟盘切换实盘

不要直接修改唯一一份模拟盘配置。应复制为独立实盘配置：

```text
config.dryrun.json
config.live.json
```

实盘前至少完成：

- 模拟盘运行时间和交易数量达到评估要求；
- 策略在相同手续费、杠杆和交易对条件下回测；
- 检查最大回撤和极端止损场景；
- 确认 `stoploss_on_exchange` 行为；
- 确认 API 禁止提现；
- 确认仓位大小和 `max_open_trades`；
- 确认数据库、日志和 Telegram Bot 均与模拟盘隔离；
- 使用小资金进行第一阶段实盘。

切换实盘的必要配置：

```json
"dry_run": false
```

这是一项高风险变更。修改后必须再次运行 `show-config`，并人工确认输出中的
`dry_run`、交易所、模式和策略。

## 15. FreqAI 和 FreqAI-RL

### 15.1 Compose 中选择镜像

普通 FreqAI：

```yaml
image: ck-quant:freqai
```

强化学习：

```yaml
image: ck-quant:freqai-rl
```

### 15.2 必须持久化的目录

```yaml
volumes:
  - "/opt/ck-quant/user_data:/freqtrade/user_data"
```

该挂载会保存：

- `user_data/models`；
- `user_data/freqaimodels`；
- TensorBoard 文件；
- 数据库和日志；
- 私有模型代码。

### 15.3 Windows 与 Linux 路径迁移

模型元数据中如果保存了 Windows 绝对路径，例如：

```text
D:\...\user_data\models\...
```

容器中将无法访问。Docker 内部路径应为：

```text
/freqtrade/user_data/models/...
```

迁移前应备份原模型元数据。无法安全修改时，使用新 `identifier` 重新训练，不要覆盖
旧模型。

### 15.4 实验隔离

每个正式实验都应使用新的：

- 策略文件或版本名；
- FreqAI `identifier`；
- 日志；
- 数据库；
- 结果记录。

不得把不同版本的数据库统计混在一起，否则无法判断修改是否有效。

## 16. 日常运行与监控

### 16.1 容器健康

```bash
docker compose ps
docker inspect ck-quant-live \
  --format 'status={{.State.Status}} restart={{.RestartCount}} oom={{.State.OOMKilled}}'
docker logs --since 1h ck-quant-live
```

重点观察：

- 容器是否持续 `running`；
- `RestartCount` 是否增加；
- 是否发生 OOM；
- 是否出现数据库锁或回滚异常；
- 是否出现交易所、DNS 或 Telegram 网络错误；
- 心跳是否持续输出。

### 16.2 交易表现

至少记录：

- 已平仓交易数量；
- 净收益；
- Profit Factor；
- 最大回撤；
- 胜率；
- 平均盈利和平均亏损；
- 多单、空单分项；
- 交易对分项；
- 退出原因；
- 是否由单一交易对或极少数交易贡献利润。

不要因为几笔短期交易立即修改策略。每次只做一个可归因变更，并为新版本保留独立
数据库、日志和模型。

### 16.3 日志轮转

长期运行时应配置主机日志轮转，避免磁盘写满。也可以为 Docker 设置日志限制：

```yaml
logging:
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"
```

这只限制 Docker 标准输出。通过 `--logfile` 写入的主机日志仍需单独轮转。

### 16.4 磁盘检查

```bash
df -h
docker system df
du -sh /opt/ck-quant/user_data/*
```

不要在未核对路径的情况下执行递归删除。数据库、模型和旧实验结果应先备份。

## 17. 升级和回滚

### 17.1 升级流程

1. 拉取源代码；
2. 使用新标签构建镜像；
3. 运行测试；
4. 备份运行目录和数据库；
5. 停止旧容器；
6. 在 Compose 中切换新镜像标签；
7. 启动并核验；
8. 保留旧镜像，直到新版本稳定。

示例：

```bash
docker build -t ck-quant:2026.08.01 .
docker compose config
docker compose up -d
```

### 17.2 回滚

将 Compose 的镜像改回旧标签：

```yaml
image: ck-quant:2026.07.30
```

然后：

```bash
docker compose up -d
```

如果新版本已经修改数据库结构，仅回滚镜像可能不够，还需要恢复升级前数据库。任何
数据库恢复都必须在容器停止后进行。

## 18. 常见故障排查

### 18.1 容器无限重启

先不要反复执行 `restart`，应收集证据：

```bash
docker inspect ck-quant-live \
  --format 'status={{.State.Status}} restart={{.RestartCount}} exit={{.State.ExitCode}} error={{.State.Error}}'
docker logs --tail 500 ck-quant-live
```

重点搜索：

```text
IntegrityError
UNIQUE constraint failed
PendingRollbackError
Not enough ... in wallet
Trying to recover
Found previously unknown order
```

如果容器持续写坏状态：

1. 停止容器；
2. 备份数据库及日志；
3. 比较数据库交易与交易所持仓；
4. 找出首个异常订单；
5. 不要直接删除数据库重新开始，除非已经明确接受历史记录丢失和持仓脱管风险。

### 18.2 `/status table` 与交易所不一致

先区分三种情况：

1. 交易所手动单：本来就不属于机器人数据库；
2. 机器人使用了错误或新建的空数据库；
3. 数据库订单数量被旧成交单污染，形成幽灵余额。

检查：

- 容器实际 `--db-url`；
- 是否挂载了预期的 `user_data`；
- 是否同时运行两个机器人；
- 每笔 Trade 的 amount；
- Binance 实际 position amount；
- 交易所止损 amount；
- 对应订单 ID 属于哪一笔 Trade。

在原因不明时，不要直接执行 `/forceexit all`，因为数据库数量错误可能导致退出数量
与交易所实际持仓不一致。

### 18.3 Telegram 只有通知，命令无响应

搜索：

```bash
docker logs --since 1h ck-quant-live 2>&1 | \
  grep -E "Telegram|getUpdates|Conflict|NetworkError"
```

最常见原因是同一 Bot Token 被另一个进程轮询。停止重复实例后，只重启当前容器。

### 18.4 WebUI 连接失败

检查：

```bash
docker compose ps
curl -I http://127.0.0.1:8080
docker logs --tail 200 ck-quant-live
```

确认：

- 配置中 `api_server.enabled=true`；
- 容器内监听 `0.0.0.0`；
- Compose 映射到主机 `127.0.0.1`；
- SSH 隧道仍在运行；
- 登录信息正确。

### 18.5 数据库被锁

可能原因：

- 两个机器人使用同一个 SQLite；
- 外部工具长时间锁住数据库；
- 网络文件系统不适合 SQLite；
- 上一次异常事务未正确回滚。

处理顺序：

1. 确认只有一个写入实例；
2. 停止机器人；
3. 备份数据库；
4. 使用 SQLite 完整性检查；
5. 根据日志定位具体事务。

```bash
sqlite3 /path/to/trades.sqlite "PRAGMA integrity_check;"
```

### 18.6 Binance 或 Telegram 网络异常

短暂的 `NetworkError` 可能自行恢复。只有持续失败并影响心跳或订单管理时才处理。

检查：

```bash
getent hosts fapi.binance.com
getent hosts api.telegram.org
docker logs --since 30m ck-quant-live
```

不要在没有证据时修改系统 DNS。先判断是偶发网络、容器 DNS、代理还是解析器问题。

## 19. 推荐目录结构

源代码与运行数据完全分离：

```text
/opt/ck-quant/
├── docker-compose.yml
├── user_data/
│   ├── config.live.json
│   ├── strategies/
│   ├── logs/
│   ├── models/
│   ├── freqaimodels/
│   └── tradesv3-ck-quant-live.sqlite
└── backups/
    ├── pre-migration-YYYYMMDD-HHMMSS/
    └── pre-upgrade-YYYYMMDD-HHMMSS/

/opt/ck-quant-source/
└── CK_Quant Git 源代码，不包含任何实盘数据
```

Windows 同样建议：

```text
D:\Eric Cheng\Documents\CK_Quant\    源代码
D:\CKQuantRuntime\                    本地运行数据
D:\CKQuantImages\                     导出的镜像
D:\CKQuantBackups\                    数据库与配置备份
```

## 20. 上线前最终检查清单

### 模拟盘

- [ ] `dry_run=true`
- [ ] 使用独立模拟盘数据库
- [ ] 使用独立 Telegram Bot
- [ ] 策略成功加载
- [ ] 交易对列表正确
- [ ] WebUI 可访问
- [ ] 容器重启次数为 0
- [ ] 单笔仓位符合预期
- [ ] 止损逻辑符合预期
- [ ] 冰山子单大小符合交易所限制

### 实盘

- [ ] 已停止旧机器人
- [ ] 已备份配置、策略、数据库和日志
- [ ] API 禁止提现并设置 IP 白名单
- [ ] `dry_run=false` 已人工确认
- [ ] 数据库路径指向原实盘数据库
- [ ] 交易所持仓、数据库和止损数量一致
- [ ] 手动仓位已单独标记和管理
- [ ] WebUI 不直接暴露公网
- [ ] Telegram Token 没有重复使用
- [ ] 已保留可回滚的旧镜像
- [ ] 首次使用小资金验证

## 21. 相关文件

- `README.md`：项目简介及上游 Freqtrade 说明；
- `CK_QUANT.md`：CK Quant 架构和冰山单简要说明；
- `Dockerfile`：普通 CK Quant 镜像；
- `docker/Dockerfile.ck-quant-freqai`：FreqAI 镜像；
- `docker/Dockerfile.ck-quant-freqai-rl`：FreqAI-RL 镜像；
- `docker-compose.ck-quant.example.yml`：Compose 示例；
- `config_examples/config_iceberg.example.json`：冰山配置示例；
- `freqtrade/ck_quant/iceberg.py`：冰山拆单参数和计算逻辑；
- `freqtrade/freqtradebot.py`：订单恢复与冰山执行逻辑；
- `ck_quant_ui/`：CK Quant WebUI 源代码。

---

建议每次升级后在本教程末尾记录实际使用的镜像标签、迁移时间、数据库备份位置和验证
结果，但不得记录明文 API Key、Telegram Token 或密码。
