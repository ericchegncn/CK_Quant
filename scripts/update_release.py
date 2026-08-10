#!/usr/bin/env python
"""更新 GitHub Release 2026.7 的发布说明（补上后续新增功能）"""
import json, os, urllib.request, urllib.error

token = ""
_tp = r"C:\Users\Eric Cheng\AppData\Local\Temp\gh_token.txt"
if os.path.exists(_tp):
    for line in open(_tp).read().splitlines():
        if line.startswith("password="):
            token = line.split("=", 1)[1].strip()
if not token:
    print("无 token"); exit(1)

body = """## CK Quant 2026.7

基于 Freqtrade 的隐私优先二次发行版。

### 🚀 新功能

#### Tick 级回测引擎（新增）
- **真实 tick 序列逐笔撮合**出场（止损/止盈触发顺序精确），替代 OHLCV bar 路径猜测
- **内存友好**：分块加载 tick（一周一个 chunk），峰值内存可控，15GB 笔记本可跑
- **策略复用**：信号在聚合 15m bar 上计算，复用 `populate_indicators` / `populate_entry_trend`
- **实测证据**：ETH 2025-07 数据上，7.1% 的交易 OHLCV 回测触发顺序判断错误，且系统性偏向乐观
- 用法：`python -m freqtrade.ck_quant.tick_backtest`（详见 [docs/advanced-tick-backtest.md](https://github.com/ericchegncn/CK_Quant/blob/main/docs/advanced-tick-backtest.md)）

#### 精确回撤（新增）
- 回测钱包余额快照现在包含**未平仓持仓的浮动盈亏**（真实账户权益）
- 回撤 / Sharpe / Sortino 基于"已实现 + 未实现"计算，修复持仓浮盈处于权益峰值时回撤低估的问题

#### 合成冰山单（Synthetic Iceberg Orders）
- 大单拆分隐藏交易意图（软件层模拟交易所冰山单）
- 入场/出场均可拆分，子单大小、补单间隔、随机扰动可配置
- 教程：[docs/advanced-iceberg.md](https://github.com/ericchegncn/CK_Quant/blob/main/docs/advanced-iceberg.md)

### 🔧 改进

- **一键发布脚本**：`scripts/release.py`（构建镜像 → 推送 Docker Hub → 打 tag → 创建 Release）
- **一键 Docker 部署**：`docker compose pull` + `docker compose up -d`
- 项目首页 README 更新（完整特性列表）

### 🐛 修复

- **fix(backtesting)**: 回测钱包余额含未平仓浮盈，回撤基于真实账户权益（详见 commit 6355ce9）

### 📦 镜像

- Docker Hub: `ericchenghz/ck-quant:stable`（与本次发布同步，digest `47697e0e`）
- 隐私优先：策略、配置、数据库、凭据、日志不进入镜像/仓库

### 版本

- 上游 Freqtrade 版本: 2026.7-dev
"""

data = json.dumps({"body": body}).encode()
req = urllib.request.Request(
    "https://api.github.com/repos/ericchegncn/CK_Quant/releases/tags/2026.7",
    data=data, method="GET",
    headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
             "User-Agent": "CK-Quant-release"},
)
proxy = urllib.request.ProxyHandler({"https": "http://127.0.0.1:7897", "http": "http://127.0.0.1:7897"})
opener = urllib.request.build_opener(proxy)
try:
    resp = opener.open(req, timeout=60)
    rel = json.loads(resp.read())
    rel_id = rel["id"]
    print("Release id:", rel_id)
    # PATCH 更新 body
    req2 = urllib.request.Request(
        f"https://api.github.com/repos/ericchegncn/CK_Quant/releases/{rel_id}",
        data=json.dumps({"body": body}).encode(), method="PATCH",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json", "User-Agent": "CK-Quant-release"},
    )
    resp2 = opener.open(req2, timeout=60)
    result = json.loads(resp2.read())
    print("✅ Release 更新成功:", result.get("html_url"))
except urllib.error.HTTPError as e:
    print(f"❌ HTTP {e.code}:", e.read().decode()[:500])
