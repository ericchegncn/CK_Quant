#!/usr/bin/env python
"""停用上游 CI 工作流：把触发条件改为仅 workflow_dispatch（手动触发）"""
import re
import os

WORKFLOWS = "D:\\Eric Cheng\\Documents\\CK_Quant\\.github\\workflows"

# 要停用的（上游带过来的、会误触发或对 fork 无用的）
DISABLE = [
    "ci.yml",                      # Freqtrade CI：release 触发全平台测试（失败源）
    "deploy-docs.yml",             # Build Documentation：release 触发（失败源）
    "pre-commit-update.yml",       # 每周自动更新 pre-commit（上游定时）
    "binance-lev-tier-update.yml", # 每周杠杆档位更新（上游定时）
    "pre-commit-types-update.yml", # PR 触发 types 更新
    "devcontainer-build.yml",      # 定时 devcontainer 预构建
    "docker-build.yml",            # workflow_call 被 ci 引用（停用无副作用）
    "packages-cleanup.yml",        # workflow_call 清理（上游用）
    "docker-update-readme.yml",    # Docker Hub 描述更新（手动）
]

# 保留的
KEEP = [
    "ck-quant-docker-publish.yml", # 我们自己的 Docker 发布
    "zizmor_action.yml",           # 安全扫描（保留评估）
]

DISABLE_TEMPLATE = """\
on:
  workflow_dispatch:
"""

for name in DISABLE:
    path = os.path.join(WORKFLOWS, name)
    if not os.path.exists(path):
        print(f"跳过（不存在）: {name}")
        continue
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # 备份
    with open(path + ".bak", "w", encoding="utf-8") as f:
        f.write(content)
    # 替换 on: 块（第一个 on: 到第一个 job: 之间）
    new_content = re.sub(
        r"^on:.*?(?=^jobs:|\Z)",
        DISABLE_TEMPLATE,
        content,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )
    if new_content == content:
        print(f"⚠️ 未匹配 on 块: {name}（手动检查）")
        continue
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print(f"✅ 已停用: {name}")

print(f"\n保留: {KEEP}")
