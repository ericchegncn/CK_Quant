FROM node:22-alpine AS ck-quant-ui

WORKDIR /ui
ENV CI=true
RUN corepack enable
COPY ck_quant_ui/package.json ck_quant_ui/pnpm-lock.yaml ck_quant_ui/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY ck_quant_ui/ ./
RUN pnpm build \
  && echo "CK Quant UI" > dist/.uiversion


FROM python:3.15.0rc3-slim-trixie AS base

# Setup env
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
# 内存优化：限制 glibc 每线程内存池（arena）数量。多线程 Python 进程默认会为
# 每个线程创建独立 arena（每个最多 64MB），低配 VPS 上造成大量碎片和 RSS 虚高。
# 2 个 arena 足以满足本应用的并发模式，可显著降低稳态内存。
ENV MALLOC_ARENA_MAX=2
ENV PATH=/home/ftuser/.local/bin:$PATH
ENV FT_APP_ENV="docker"
LABEL org.opencontainers.image.title="CK Quant"
LABEL org.opencontainers.image.description="Privacy-first Freqtrade distribution with resilient recovery and iceberg execution"
LABEL org.opencontainers.image.licenses="GPL-3.0"
LABEL org.opencontainers.image.source="https://github.com/ericchegncn/CK_Quant"

# Prepare environment
RUN mkdir /freqtrade \
  && apt-get update \
  && apt-get -y install --no-install-recommends sudo libatlas3-base curl sqlite3 libgomp1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && useradd -u 1000 -G sudo -U -m -s /bin/bash ftuser \
  && chown ftuser:ftuser /freqtrade \
  # Allow sudoers
  && echo "ftuser ALL=(ALL) NOPASSWD: /bin/chown" >> /etc/sudoers

WORKDIR /freqtrade

# Install dependencies
FROM base AS python-deps
RUN  apt-get update \
  && apt-get -y install --no-install-recommends build-essential libssl-dev git libffi-dev libgfortran5 pkg-config cmake gcc \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --upgrade pip wheel

# Install dependencies
COPY --chown=ftuser:ftuser requirements.txt requirements-hyperopt.txt /freqtrade/
USER ftuser
RUN  pip install --user --no-cache-dir "numpy<3.0" \
  && pip install --user --no-cache-dir -r requirements-hyperopt.txt

# Copy dependencies to runtime-image
FROM base AS runtime-image

COPY --from=python-deps --chown=ftuser:ftuser /home/ftuser/.local /home/ftuser/.local

USER ftuser
# Install and execute
COPY --chown=ftuser:ftuser . /freqtrade/

RUN if find /freqtrade -type f \( \
      -name 'CK_*.py' \
      -o -name 'test_ck_*.py' \
      -o -iname 'Freqtrade*.txt' \
      -o -path '*/user_data/strategies/*' \
      -o -path '*/remote-deploy/*' \
      -o -path '*/.hotfix-build-*/*' \
    \) \
      -print -quit | tee /dev/stderr | grep -q .; then \
      echo 'Refusing to build: proprietary strategy source detected in Docker context.' >&2; \
      exit 1; \
    fi \
  && if grep -RIlE \
      'from user_data\.strategies\.CK_|import user_data\.strategies\.CK_|class CK_[A-Z]' \
      /freqtrade --include='*.py' | grep -q .; then \
      echo 'Refusing to build: proprietary CK strategy logic detected.' >&2; \
      exit 1; \
    fi \
  && if grep -RIlE \
      'CK_[A-Z][A-Za-z0-9_]*(_15m|_5m|_1m)|remote-deploy-marker|live-deployment-marker' \
      /freqtrade | grep -q .; then \
      echo 'Refusing to build: private deployment marker detected.' >&2; \
      exit 1; \
    fi \
  # 第 4 条守卫（2026-10-14）：前三条只查策略「源码」与部署标记，于是
  # 「策略名写在文本/文档文件里」这种回归能一路烤进公开镜像 —— 实测一份中文说明
  # 文档里的 CK_* 策略名确实进了全部已发布镜像（本仓 docker-compose.yml 头部的
  # 注释也曾把私有策略名带进公开仓库）。本守卫扫文件「内容」里的私有 CK_* 名字：
  #   1) 文本类后缀（.md/.txt/.yml/.yaml/.json/...）；
  #   2) 不限后缀的全量文本扫描，覆盖 .bak / 无后缀 / 其它扩展名。
  # 白名单只保留产品名与公开的 CK_QUANT_* 环境变量契约，其余 CK_ 开头的大驼峰
  # 名字（私有策略类名）一律拒绝构建。\b 保证 TICK_SIZE / CHECK_BATCH 这类
  # 子串不会误报。
  && if { \
      grep -RhoIE '\bCK_[A-Z][A-Za-z0-9_]*' /freqtrade \
        --include='*.md' --include='*.txt' --include='*.yml' --include='*.yaml' \
        --include='*.json' --include='*.toml' --include='*.cfg' --include='*.ini' \
        --include='*.rst' --include='*.html' --include='*.js' --include='*.ts' \
        --include='*.vue' --include='*.css' --include='*.sh' ; \
      grep -RhoIE '\bCK_[A-Z][A-Za-z0-9_]*' /freqtrade ; \
    } | grep -vwE 'CK_Quant|CK_Quant_Rust|CK_Quant_Hedge|CK_QUANT(_[A-Z]+)*' \
      | sort -u | tee /dev/stderr | grep -q .; then \
      echo 'Refusing to build: private CK strategy name found in the Docker context (names listed above).' >&2; \
      grep -RIlE '\bCK_[A-Z][A-Za-z0-9_]*' /freqtrade >&2; \
      exit 1; \
    fi \
  && pip install -e . --user --no-cache-dir \
  && mkdir -p /freqtrade/user_data/ /freqtrade/freqtrade/rpc/api_server/ui/installed/

COPY --from=ck-quant-ui --chown=ftuser:ftuser \
  /ui/dist/ /freqtrade/freqtrade/rpc/api_server/ui/installed/

ENTRYPOINT ["freqtrade"]
# Default to trade mode
CMD [ "trade" ]
