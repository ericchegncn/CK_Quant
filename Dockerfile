FROM node:22-alpine AS ck-quant-ui

WORKDIR /ui
ENV CI=true
RUN corepack enable
COPY ck_quant_ui/package.json ck_quant_ui/pnpm-lock.yaml ck_quant_ui/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY ck_quant_ui/ ./
RUN pnpm build \
  && echo "CK Quant UI" > dist/.uiversion


FROM python:3.15.0b3-slim-trixie AS base

# Setup env
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
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

RUN pip install -e . --user --no-cache-dir \
  && mkdir -p /freqtrade/user_data/ /freqtrade/freqtrade/rpc/api_server/ui/installed/

COPY --from=ck-quant-ui --chown=ftuser:ftuser \
  /ui/dist/ /freqtrade/freqtrade/rpc/api_server/ui/installed/

ENTRYPOINT ["freqtrade"]
# Default to trade mode
CMD [ "trade" ]
