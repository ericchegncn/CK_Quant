#!/usr/bin/env bash
# CK Quant 全自动 Docker 安装脚本（无交互，国内源优先，多级回退）
# 支持: Ubuntu / Debian / CentOS / Rocky / AlmaLinux (x86_64 / arm64)
set -e

log()  { echo "[docker-install] $*"; }
fail() { echo "[docker-install] ❌ $*"; exit 1; }

log "=== CK Quant Docker 全自动安装 ==="

# 0. 检查是否已安装
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  log "Docker 已安装: $(docker --version) / $(docker compose version)"
  exit 0
fi

# 1. 检测发行版
if [ -f /etc/os-release ]; then
  . /etc/os-release
  OS_ID="$ID"
  OS_VER="$VERSION_ID"
else
  OS_ID="unknown"
fi
log "系统: $OS_ID $OS_VER ($(uname -m))"

# 2. 安装依赖（优先国内源，静默）
install_deps() {
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq curl ca-certificates gnupg lsb-release >/dev/null 2>&1 || true
  elif command -v yum >/dev/null 2>&1; then
    yum install -y -q curl ca-certificates >/dev/null 2>&1 || true
  fi
}

# 3. 尝试方案A：官方 get.docker.com（全自动，无交互）
try_official() {
  log "尝试官方安装脚本 (get.docker.com)..."
  if curl -fsSL --connect-timeout 10 https://get.docker.com -o /tmp/get-docker.sh 2>/dev/null; then
    sh /tmp/get-docker.sh >/tmp/docker-install.log 2>&1 && return 0
    log "官方脚本失败，尝试国内源..."
  fi
  return 1
}

# 4. 尝试方案B：阿里云镜像源（全自动，无交互）
try_aliyun() {
  log "尝试阿里云镜像源安装..."
  local arch="$(uname -m)"
  local docker_arch=""
  case "$arch" in
    x86_64)  docker_arch="amd64" ;;
    aarch64) docker_arch="arm64" ;;
    *)       docker_arch="$arch" ;;
  esac

  if command -v apt-get >/dev/null 2>&1; then
    # Debian/Ubuntu
    local distro="$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]' || echo "$OS_ID")"
    local codename="$(lsb_release -cs 2>/dev/null || echo "")"
    [ -z "$codename" ] && codename="$(grep -oP 'VERSION_CODENAME=\K.*' /etc/os-release 2>/dev/null || echo bookworm)"
    mkdir -p /etc/apt/keyrings
    curl -fsSL --connect-timeout 10 "https://mirrors.aliyun.com/docker-ce/linux/$distro/gpg" \
      -o /etc/apt/keyrings/docker.asc 2>/dev/null || return 1
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$docker_arch signed-by=/etc/apt/keyrings/docker.asc] https://mirrors.aliyun.com/docker-ce/linux/$distro $codename stable" \
      > /etc/apt/sources.list.d/docker.list
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1 && return 0
  elif command -v yum >/dev/null 2>&1; then
    # CentOS/Rocky/Alma
    yum install -y -q yum-utils >/dev/null 2>&1 || true
    yum-config-manager --add-repo "https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo" >/dev/null 2>&1 || return 1
    yum install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null 2>&1 && return 0
  fi
  return 1
}

# 5. 安装
install_deps
if ! try_official; then
  try_aliyun || fail "Docker 安装失败，请手动安装"
fi

# 6. 启动 + 开机自启
log "启动 Docker 并设置开机自启..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable docker >/dev/null 2>&1 || true
  systemctl start docker >/dev/null 2>&1 || service docker start || true
elif command -v service >/dev/null 2>&1; then
  service docker start >/dev/null 2>&1 || true
fi

# 7. 验证
sleep 2
if docker --version >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  log "✅ Docker 安装成功: $(docker --version)"
  log "✅ Compose: $(docker compose version)"
  log "✅ 开机自启已配置"
  exit 0
else
  fail "Docker 安装后验证失败"
fi
