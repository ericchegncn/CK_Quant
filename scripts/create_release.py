#!/usr/bin/env python
"""创建 GitHub Release 2026.7"""
import json, subprocess, urllib.request, os

# 从 git credential 读取 token
token = ""
_token_path = r"C:\Users\Eric Cheng\AppData\Local\Temp\gh_token.txt"
if os.path.exists(_token_path):
    for line in open(_token_path).read().splitlines():
        if line.startswith("password="):
            token = line.split("=", 1)[1].strip()
if not token:
    print("无 token")
    exit(1)

body = """## CK Quant 2026.7

基于 Freqtrade 的隐私优先二次发行版，包含：

### 本次修复
- **fix(backtesting)**: 钱包余额快照现在包含未平仓持仓的浮动盈亏（用最新收盘价估算），回撤/Sharpe/Sortino 基于**真实账户权益**（已实现 + 未实现）计算，而非仅已实现利润。修复了持仓浮盈处于权益峰值时回测回撤低估的问题。

### 核心特性
- crash-safe 交易所订单恢复（应对快速反手交易）
- 可选合成冰山委托（iceberg execution）用于入场和常规出场
- 响应式半透明卡片式 CK Quant UI
- 可复现的 CPU / FreqAI Docker 镜像定义
- 一键 Docker 部署（`docker compose pull` + `docker compose up -d`）

### 镜像
- Docker Hub: `ericchenghz/ck-quant:stable`（与本次发布同步）
- 隐私优先：策略、配置、数据库、凭据、日志不进入镜像/仓库

### 版本
- Freqtrade 上游版本: 2026.7-dev
"""

data = json.dumps({
    "tag_name": "2026.7",
    "name": "CK Quant 2026.7",
    "body": body,
    "draft": False,
    "prerelease": False,
}).encode()

req = urllib.request.Request(
    "https://api.github.com/repos/ericchegncn/CK_Quant/releases",
    data=data,
    method="POST",
    headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "CK-Quant-release",
    },
)
# 走 Clash 代理
proxy = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7897", "http": "http://127.0.0.1:7897"})
opener = urllib.request.build_opener(proxy)

try:
    resp = opener.open(req, timeout=60)
    result = json.loads(resp.read())
    print("✅ Release 创建成功:", result.get("html_url"))
except urllib.error.HTTPError as e:
    print(f"❌ HTTP {e.code}:", e.read().decode()[:500])
