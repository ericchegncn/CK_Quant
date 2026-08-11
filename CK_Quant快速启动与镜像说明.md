# CK Quant 快速启动与镜像说明

这份说明用于在 Windows、Linux 或服务器上通过 Docker 部署和维护
CK Quant。公开镜像和源代码地址如下：

- GitHub：<https://github.com/ericchegncn/CK_Quant>
- Docker 镜像：`ericchenghz/ck-quant:stable`
- Docker Compose：<https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml>

公开镜像只包含 CK Quant 程序和 WebUI，不包含个人配置、策略、交易所
API Key、Telegram Token、数据库、日志或训练模型。所有私有数据都保存在
部署机器的 `CK_Quant/user_data` 目录中。

## 一、当前本机 CK_Trailing 模拟盘

- Docker 镜像：`ck-quant:local`
- 容器：`CK_Quant`
- 策略：`CK_Trailing`
- 配置：`user_data/config_Trailing.json`
- 日志：`user_data/logs/CK_Quant_Trailing_dryrun.log`
- 数据库：`user_data/tradesv3_CK_Quant_Trailing_dryrun.sqlite`
- WebUI：<http://127.0.0.1:8080>

本机这个已有实例使用 `/CK_Quant/user_data` 作为容器内用户目录，因此它的
启动命令必须包含：

```text
--userdir /CK_Quant/user_data
```

新部署使用公开的标准 `docker-compose.yml`，容器内用户目录统一为
`/freqtrade/user_data`，不要把两套路径混用。

## 二、Linux 或云服务器首次部署

### 1. 安装 Docker

建议优先使用 Docker 官方文档安装。也可使用以下第三方一键脚本，但执行任何
第三方脚本前应先自行检查脚本内容：

```bash
bash <(curl -sSL https://cdn.jsdelivr.net/gh/SuperManito/LinuxMirrors@main/DockerInstallation.sh)
```

验证 Docker 和 Compose：

```bash
docker --version
docker compose version
```

### 2. 创建默认目录并下载 Compose

```bash
mkdir -p CK_Quant
cd CK_Quant

curl -L \
  https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml

curl -L \
  https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/.env.example \
  -o .env
```

### 3. 拉取公开镜像

```bash
docker compose pull
```

镜像由 Docker Engine 管理，不会作为普通文件出现在 `CK_Quant` 文件夹中。
可用以下命令查看：

```bash
docker image ls ericchenghz/ck-quant
```

### 4. 创建本地私有用户目录

```bash
docker compose run --rm ck-quant create-userdir --userdir user_data
```

这会创建类似以下结构：

```text
CK_Quant/
├── docker-compose.yml
├── .env
└── user_data/
    ├── strategies/
    ├── data/
    ├── logs/
    ├── models/
    └── hyperopts/
```

### 5. 创建配置或放入已有配置

新用户可交互式创建配置：

```bash
docker compose run --rm ck-quant \
  new-config --config user_data/config.json
```

已有配置时，把配置复制到 `user_data`，例如：

```text
user_data/config_Trend.json
```

不要把真实 API Key、Secret 或 Telegram Token 写进 GitHub 仓库。

### 6. 放入策略

把策略文件复制到：

```text
user_data/strategies/
```

例如：

```text
user_data/strategies/MyPrivateStrategy.py
```

`.env` 中的 `CK_QUANT_STRATEGY` 必须填写 Python 文件内部的策略类名，
不一定等于文件名。

### 7. 修改 `.env`

首次部署至少检查这些值：

```dotenv
CK_QUANT_IMAGE=ericchenghz/ck-quant:stable
CK_QUANT_CONTAINER_NAME=CK_Quant
CK_QUANT_CONFIG=config_Trend.json
CK_QUANT_STRATEGY=MyPrivateStrategy
CK_QUANT_DATABASE=tradesv3.sqlite
CK_QUANT_LOGFILE=ck-quant.log
CK_QUANT_WEBUI_BIND=127.0.0.1
CK_QUANT_WEBUI_PORT=8080
```

其中：

- `CK_QUANT_CONFIG` 是 `user_data` 内的配置文件名；
- `CK_QUANT_STRATEGY` 是策略类名；
- `CK_QUANT_DATABASE` 是数据库文件名；
- `CK_QUANT_LOGFILE` 是日志文件名；
- `CK_QUANT_WEBUI_BIND=127.0.0.1` 表示 WebUI 只允许本机访问；
- 不要在没有防火墙、认证和 HTTPS 的情况下把 WebUI 直接暴露到公网。

### 8. 启动前检查

第一次运行或切换实盘前，必须确认配置中的运行模式：

```json
"dry_run": true
```

先检查 Compose 最终解析结果：

```bash
docker compose config
```

检查配置是否可加载：

```bash
docker compose run --rm ck-quant \
  show-config \
  --userdir /freqtrade/user_data \
  --config /freqtrade/user_data/config_Trend.json
```

检查策略是否能被找到：

```bash
docker compose run --rm ck-quant \
  list-strategies \
  --userdir /freqtrade/user_data \
  --config /freqtrade/user_data/config_Trend.json
```

### 9. 启动 CK Quant

```bash
docker compose up -d
docker compose ps
docker compose logs -f --tail 200
```

按 `Ctrl+C` 只会退出日志查看，不会停止容器。

如果配置启用了 API Server，且端口保持默认设置，本机 WebUI 地址为：

```text
http://127.0.0.1:8080
```

远程服务器建议通过 SSH 隧道访问，而不是直接开放 8080 端口：

```bash
ssh -L 8080:127.0.0.1:8080 用户名@服务器地址
```

然后在本地浏览器打开 <http://127.0.0.1:8080>。

## 三、Windows Docker Desktop 首次部署

在 PowerShell 中执行：

```powershell
New-Item -ItemType Directory -Path "$HOME\CK_Quant" -Force
Set-Location "$HOME\CK_Quant"

Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml" `
  -OutFile "docker-compose.yml"

Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/.env.example" `
  -OutFile ".env"

docker compose pull
docker compose run --rm ck-quant create-userdir --userdir user_data
docker compose run --rm ck-quant new-config --config user_data/config.json
```

然后：

1. 将策略放入 `user_data\strategies\`；
2. 将已有配置放入 `user_data\`，或编辑新生成的 `config.json`；
3. 编辑 `.env` 中的配置文件名和策略类名；
4. 确认模拟盘配置为 `"dry_run": true`；
5. 启动并检查日志。

```powershell
docker compose config
docker compose up -d
docker compose ps
docker compose logs -f --tail 200
```

## 四、常用管理命令

以下命令都在包含 `docker-compose.yml` 的 `CK_Quant` 目录中执行：

```bash
# 启动或恢复
docker compose up -d

# 查看状态
docker compose ps

# 持续查看最近200行日志
docker compose logs -f --tail 200

# 停止但保留容器
docker compose stop

# 启动已停止的容器
docker compose start

# 重启
docker compose restart

# 删除容器和网络，保留本地 user_data
docker compose down

# 修改 Compose 或 .env 后重新创建容器
docker compose up -d --force-recreate
```

`docker compose down` 不会删除通过目录挂载的 `user_data`。不要随意添加
`--volumes`，除非已经确认不会删除需要的数据。

## 五、升级到最新 CK Quant 镜像

升级前先停止机器人并备份数据库、配置和策略：

```bash
cd CK_Quant
docker compose stop
```

至少备份：

```text
user_data/config*.json
user_data/strategies/
user_data/*.sqlite
user_data/*.sqlite-wal
user_data/*.sqlite-shm
```

再执行：

```bash
docker compose pull
docker compose up -d --force-recreate
docker compose ps
docker compose logs --tail 200
```

确认新容器稳定、订单与交易所一致后，再继续正常运行。

## 六、使用已有配置和策略迁移到 CK Quant

从 Freqtrade 迁移时，不需要改变策略逻辑。基本流程是：

1. 停止旧 Freqtrade 容器，避免两个机器人同时交易；
2. 完整备份原 `user_data`；
3. 将配置、策略和数据库复制到新的 `CK_Quant/user_data`；
4. 在 `.env` 中设置正确的配置文件名和策略类名；
5. 保持原有 `dry_run` 或实盘模式，不擅自改变；
6. 先运行 `show-config` 和 `list-strategies`；
7. 确认没有旧实例后，再启动唯一一个 CK Quant 容器；
8. 对实盘检查交易所持仓、Bot数据库、止损单和订单数量是否一致。

不要让旧 Freqtrade 和新 CK Quant 同时读取同一个数据库或使用同一 Telegram
Bot，否则可能出现数据库并发、重复下单或 Telegram `getUpdates` 冲突。

## 七、为什么项目目录里没有镜像文件

`docker build` 和 `docker compose pull` 创建或下载的是 Docker Engine 管理的
镜像，不是项目目录中的普通文件。可在 Docker Desktop 的 **Images** 页面查看，
也可以运行：

```bash
docker image ls
docker image inspect ericchenghz/ck-quant:stable
```

Compose 直接引用 Docker Engine 中的镜像，因此日常运行不需要 `.tar` 文件。

## 八、导出和导入离线镜像

需要复制到不能访问 Docker Hub 的电脑时，可导出 `.tar`：

```powershell
New-Item -ItemType Directory -Path ".\docker-images" -Force
docker save `
  --output ".\docker-images\ck-quant-stable-YYYY-MM-DD.tar" `
  ericchenghz/ck-quant:stable
```

另一台电脑导入：

```powershell
docker load --input ".\docker-images\ck-quant-stable-YYYY-MM-DD.tar"
docker image ls ericchenghz/ck-quant
```

`.tar` 仅包含镜像，不包含部署机器上的 `user_data`。配置、策略、数据库和模型
必须单独备份和复制。

本机之前导出的本地开发镜像位于：

```text
D:\Eric Cheng\Documents\CK_Quant\docker-images\ck-quant-local-2026-07-31.tar
```

## 九、本地源码构建

只有开发 CK Quant 本身时才需要从源码构建：

```powershell
Set-Location "D:\Eric Cheng\Documents\CK_Quant"
docker build --tag ck-quant:local .
docker image ls ck-quant
```

使用本地镜像时，可在 `.env` 中设置：

```dotenv
CK_QUANT_IMAGE=ck-quant:local
```

再重新创建容器：

```powershell
docker compose up -d --force-recreate
```

普通部署建议直接使用：

```text
ericchenghz/ck-quant:stable
```

这样可直接通过 `docker compose pull` 更新，无需在服务器上保存源码或重新构建。

## 十、常见故障排查

### 容器不断重启

先不要删除数据库，查看真实错误：

```bash
docker compose ps
docker inspect CK_Quant --format '{{.RestartCount}} {{.State.Status}} {{.State.Error}}'
docker compose logs --tail 300
```

重点检查：

- `.env` 中的配置文件名和策略类名是否正确；
- 配置和策略是否确实位于 `user_data`；
- 命令是否包含 `--userdir /freqtrade/user_data`；
- 数据库是否被另一个容器或主机进程同时使用；
- Telegram Bot 是否被另一个实例轮询；
- 交易所 API、DNS、时钟和网络是否正常。

### 找不到策略

确认策略类名：

```bash
docker compose run --rm ck-quant \
  list-strategies \
  --userdir /freqtrade/user_data \
  --config /freqtrade/user_data/config.json
```

`.env` 中应填写类名，例如：

```dotenv
CK_QUANT_STRATEGY=MyPrivateStrategy
```

### WebUI 无法访问

检查：

```bash
docker compose ps
docker compose logs --tail 200
```

同时确认配置已启用 `api_server`，端口没有被占用，且
`CK_QUANT_WEBUI_BIND` 符合访问方式。公网部署必须增加认证、防火墙和 HTTPS。

### 修改 `.env` 后没有生效

环境变量变化通常需要重新创建容器：

```bash
docker compose up -d --force-recreate
```

## 十一、数据库和私有数据安全

不要在机器人运行时，从主机直接用 SQLite 工具修改活动数据库及其 WAL 文件。
需要复制或维修数据库时，先执行：

```bash
docker compose stop
```

必须保持私有且不能上传 GitHub 的内容包括：

- `user_data/config*.json`；
- `user_data/strategies/` 中的私有策略；
- 交易所 API Key 和 Secret；
- Telegram Token；
- SQLite 数据库及 WAL/SHM 文件；
- 日志、FreqAI 模型和交易数据；
- 服务器 IP、SSH 密钥及其他凭据。

每次提交 GitHub 前，都应运行：

```bash
git status
```

确认上述私有文件没有被暂存或提交。
