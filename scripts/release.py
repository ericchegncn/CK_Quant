#!/usr/bin/env python
"""
CK Quant 一键发布脚本
=====================
流程：构建本地镜像 → 推送 Docker Hub → 打 git tag → 创建 GitHub Release

用法：
    python scripts/release.py 2026.8 [--message "自定义发布说明"]
    python scripts/release.py 2026.8 --dry-run        # 只显示将执行的步骤

前置条件：
- 已登录 docker（docker login）
- git credential 已配置（Git Credential Manager）
- Clash 代理运行在 127.0.0.1:7897（推送 GitHub 用）

版本规则（沿用 freqtrade 风格）：
- tag/Release 名 = 年月号，如 2026.8
- Docker Hub 镜像 = ericchenghz/ck-quant:{version} + :stable + :latest
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date

REPO = "ericchegncn/CK_Quant"
DOCKER_IMAGE = "ericchenghz/ck-quant"
PROXY = "http://127.0.0.1:7897"
TOKEN_FILE = r"C:\Users\Eric Cheng\AppData\Local\Temp\gh_token.txt"

DEFAULT_BODY_TEMPLATE = """## CK Quant {version}

基于 Freqtrade 的隐私优先二次发行版。

### 本次更新
（待补充：主要变更点）

### 核心特性
- crash-safe 交易所订单恢复（应对快速反手交易）
- 可选合成冰山委托（iceberg execution）用于入场和常规出场
- 响应式半透明卡片式 CK Quant UI
- 可复现的 CPU / FreqAI Docker 镜像定义
- 一键 Docker 部署（`docker compose pull` + `docker compose up -d`）

### 镜像
- Docker Hub: `{docker_image}:stable`（与本次发布同步）
- 隐私优先：策略、配置、数据库、凭据、日志不进入镜像/仓库
"""


def run(cmd, check=True, capture=False):
    """执行命令（支持代理环境变量）"""
    env = os.environ.copy()
    env.setdefault("HTTPS_PROXY", PROXY)
    env.setdefault("HTTP_PROXY", PROXY)
    env.setdefault("ALL_PROXY", PROXY)
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, shell=False)
        if check and r.returncode != 0:
            print(f"❌ 命令失败: {' '.join(cmd)}\n{r.stderr}")
            sys.exit(1)
        return r.stdout.strip()
    r = subprocess.run(cmd, env=env, shell=False)
    if check and r.returncode != 0:
        print(f"❌ 命令失败: {' '.join(cmd)}")
        sys.exit(1)
    return ""


def get_token():
    """从 git credential 读取 GitHub token"""
    # 让 git credential fill 输出 token
    r = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    return ""


def create_github_release(version: str, body: str, token: str):
    """通过 GitHub API 创建 Release"""
    data = json.dumps({
        "tag_name": version,
        "name": f"CK Quant {version}",
        "body": body,
        "draft": False,
        "prerelease": False,
    }).encode()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/releases",
        data=data, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "CK-Quant-release",
        },
    )
    proxy = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
    opener = urllib.request.build_opener(proxy)
    try:
        resp = opener.open(req, timeout=60)
        result = json.loads(resp.read())
        print(f"✅ GitHub Release: {result.get('html_url')}")
    except urllib.error.HTTPError as e:
        # 如果 tag 已存在但 Release 没有，尝试更新
        print(f"❌ HTTP {e.code}: {e.read().decode()[:400]}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    version = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    custom_msg = None
    if "--message" in sys.argv:
        i = sys.argv.index("--message")
        custom_msg = sys.argv[i + 1]

    if not version.startswith("20"):
        print(f"❌ 版本号格式应为年月号，如 2026.8（收到: {version}）")
        sys.exit(1)

    body = custom_msg or DEFAULT_BODY_TEMPLATE.format(
        version=version, docker_image=DOCKER_IMAGE
    )

    print(f"📦 CK Quant {version} 发布流程\n")

    # 1. 确认 git 状态干净（除了 untracked）
    status = run(["git", "status", "--porcelain"], capture=True)
    modified = [l for l in status.splitlines() if l.startswith(" M") or l.startswith("M ")]
    if modified and not dry_run:
        print("⚠️  有未提交的修改:")
        for m in modified[:10]:
            print(f"   {m}")
        r = input("  继续发布？（未提交修改不会包含在发布中）[y/N]: ")
        if r.lower() != "y":
            print("已取消")
            sys.exit(0)

    # 2. 构建本地镜像
    print("🔨 构建镜像 ck-quant:local ...")
    if not dry_run:
        run(["docker", "build", "-t", "ck-quant:local", "."])
    print("✅ 镜像构建完成")

    # 3. 推送 Docker Hub
    for tag in [version, "stable", "latest"]:
        full = f"{DOCKER_IMAGE}:{tag}"
        print(f"📤 推送 {full} ...")
        if not dry_run:
            run(["docker", "tag", "ck-quant:local", full])
            run(["docker", "push", full])
        print(f"✅ {full} 已推送")

    # 4. 打 git tag 并推送
    print(f"🏷️  打 tag {version} ...")
    if not dry_run:
        run(["git", "tag", "-a", version, "-m", f"CK Quant {version}"])
        run(["git", "push", "origin", version])
    print(f"✅ tag {version} 已推送")

    # 5. 创建 GitHub Release
    print("🚀 创建 GitHub Release ...")
    if not dry_run:
        token = get_token()
        if not token:
            print("❌ 无法获取 GitHub token（检查 git credential 配置）")
            sys.exit(1)
        create_github_release(version, body, token)
    else:
        print("（dry-run）Release body 预览:")
        print("---")
        print(body)
        print("---")

    print("\n🎉 发布完成！")


if __name__ == "__main__":
    main()
