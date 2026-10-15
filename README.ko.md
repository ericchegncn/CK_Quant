# CK Quant

**프라이버시를 최우선으로 한 Freqtrade 배포판 — 웹 및 Android 원격 관리 지원**

**[English](README.md) | [中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [日本語](README.ja.md) | [한국어](README.ko.md)**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## 기능

| 기능 | 설명 |
|---|---|
| **충돌 안전 주문 복구** | 급격한 정지-반전 매매 이후 거래소 주문을 복원하여 무한 재시작 루프를 방지 |
| **합성 아이스버그 주문** | 대량 주문을 진입/청산 시 숨겨진 조각으로 분할하는 선택 기능 |
| **카드 기반 반응형 UI** | 반투명하고 모바일 친화적인 WebUI, 7개 로케일 지원 (zh-CN, zh-TW, en, de, ja, fr, ko) |
| **다국어 봇** | Telegram 알림, 명령, 채팅 오류가 동일한 7개 로케일을 사용하며 `/language`로 채팅별 전환 가능 |
| **인증된 관리자 워크스페이스** | 설정과 전략을 온라인에서 편집/검증하고, 자동 백업과 안전한 리로드/재시작 지원 |
| **Android 앱** | 휴대폰에서 서버에 접속해 봇을 관리하고 거래를 직접 조작 |
| **CK Quant 데스크톱** | 초보자용 Windows 워크스페이스 — 오프라인 영구 기기 라이선스, 자격 증명 암호화, AI 채팅, 순차 백테스트, 결정론적 G1-G10 게이트, 모니터링, 확인 후 모의 투자 배포 |
| **Tick 레벨 백테스트 엔진** | OHLCV 봉 경로를 추정하는 대신 실제 Tick 시퀀스로 청산을 매칭하는 메모리 친화적 엔진 |
| **평가손익 기준 드로다운** | 실현 손익과 미실현 손익을 합산한 자본 드로다운 |
| **상승/하락 페어리스트** | 변동률 기준으로 페어 순위 산정(상승 상위 + 하락 상위), 거래량/정적 리스트와 혼합 가능 |
| **실시간 수익 지수** | 미체결 거래의 미실현 손익까지 포함 — 봇이 실행되는 동안 통계가 뒤처지지 않음 |
| **공개 쇼케이스 페이지** | 계정이 없는 방문자를 위한 선택적 읽기 전용 공개 개요(`/showcase`) — 집계 수치만 제공하며 페어, 전략명, 거래 내역, 키는 포함하지 않음 |
| **원클릭 릴리스** | 빌드 → Docker Hub 푸시 → 태그 → GitHub Release를 명령 하나로 수행 |
| **원클릭 전체 청산** | 목록에 표시된 bot 의 모든 포지션을 한 번에 청산하는 WebUI 버튼(PC·모바일). LIVE bot 이 포함되면 2차 확인 |


---

## CK Quant 데스크톱

Windows 데스크톱 앱은 [`desktop/`](desktop/)에 있습니다. **10,000 USDT 1회 결제, 기기 코드에 바인딩되는 영구 라이선스**를 사용하며 반복 구독은 없습니다. 고객용 앱에는 공개 검증 키만 포함되며, 등록 코드는 별도로 분리되어 Git에서 제외된 제조사 콘솔에서 서명됩니다.

원클릭 연구 워크플로는 Freqtrade가 공개한 `SampleStrategy`를 15m에 맞게 적용한 버전에서 출발하며, 사용자의 비공개 전략을 템플릿으로 삼지 않습니다. 가져온 비공개 전략, 자동 생성된 변형, API 자격 증명, 백테스트 산출물과 감사 데이터는 모두 로컬 애플리케이션 데이터 디렉터리에만 저장되고 Git과 릴리스 패키지에서 제외됩니다.

모든 백테스트는 로컬 CK Quant Docker 컨테이너를 통해 순차적으로 실행됩니다. 통계적 근거가 부족한 항목은 **평가되지 않음**으로 표시되며, 모의 투자 배포에는 사용자의 명시적 확인이 필요합니다. 실자금 투입 활성화는 별도의 수동 확인 단계로 남아 있습니다.

설치, 활성화 및 개발에 관한 자세한 내용은 [`desktop/README.md`](desktop/README.md)를 참조하십시오.

---

## 설치 (Docker)

**사전 요구 사항**: Compose v2가 포함된 Docker. Python 환경은 필요하지 않습니다.

```bash
mkdir CK_Quant
cd CK_Quant

# Download the compose file
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml

# Pull the image and create your user directory
docker compose pull
docker compose run --rm CK_Quant create-userdir --userdir user_data
> The compose service runs with `working_dir: /CK_Quant`, so relative
> paths like `user_data` land inside the mounted volume.
> (Absolute path also works: `--userdir /CK_Quant/user_data`)


# Generate a starter config
docker compose run --rm CK_Quant new-config --config user_data/config.json
```

**이미지 선택**:

| 이미지 | 용도 |
|---|---|
| `ericchenghz/ck-quant:stable` | 일반 거래 (권장) |
| `ericchenghz/ck-quant:stable-freqai` | FreqAI 모델 (LightGBM/XGBoost/RF) |
| `ericchenghz/ck-quant:stable-freqai-rl` | FreqAI + PyTorch 강화 학습 |

`.env`에서 `CK_QUANT_IMAGE`를 설정하여 전환합니다.

### 최초 설정

`new-config` 실행 후 `user_data/config.json`을 편집하여 핵심 항목을 설정합니다:

```jsonc
{
    "exchange": {
        "name": "binance",
        "key": "YOUR_API_KEY",       // from the exchange (enable futures trading)
        "secret": "YOUR_API_SECRET", // keep it secret — it never enters the image
        "pair_whitelist": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    },
    "stake_amount": 100,             // fixed amount per trade
    "max_open_trades": 5,
    "dry_run": true                  // start in paper-trading mode!
}
```

> **항상 `dry_run: true`**(모의 투자)로 시작하십시오. 봇의 동작 방식과 예상 손익을
> 충분히 이해한 뒤에만 `false`로 전환하십시오. 선물 거래의 경우 API 키를 발급할 때
> **Enable Futures**를 체크해야 합니다.

### 전략을 넣고 시작하기

```bash
# 1. Copy your private strategy into user_data/strategies/
# 2. Copy .env.example to .env and set CK_QUANT_STRATEGY to your class name
cp .env.example .env
#    CK_QUANT_STRATEGY=YourStrategyName

# 3. Start
docker compose up -d
docker compose logs -f --tail 200
```

WebUI는 기본적으로 <http://127.0.0.1:8080>에서 수신 대기합니다(`CK_QUANT_WEBUI_BIND` / `CK_QUANT_WEBUI_PORT`로 변경 가능).

설정, 전략, 데이터베이스, 자격 증명, 모델, 로그는 모두 로컬 `user_data` 디렉터리에 저장됩니다 — **민감한 정보는 이미지에 절대 포함되지 않습니다**.

> **보안**: 관리자/API 포트를 공용 인터넷에 노출하지 마십시오. HTTPS 리버스
> 프록시나 신뢰할 수 있는 VPN을 사용하고, 강력하고 고유한 비밀번호와 JWT
> 시크릿을 설정하십시오. 먼저 `dry_run` 인스턴스에서 검증하십시오.

---

## 기능 가이드

### 1. 다국어 WebUI 및 Android 앱

WebUI는 7개 로케일과 인증된 관리자 워크스페이스를 제공합니다:

- 저장 전 서버 측 검증과 함께 일반 또는 전체 설정 파라미터 편집
- 전략 파라미터 또는 전략 파일을 온라인에서 편집
- 설정/전략 자동 백업, 저장 후 안전한 리로드 또는 재시작
- Freqtrade API를 통한 런타임 상태 조회, 주문 및 포지션 관리
- 관리자 감사 로그 검토

관리자 기능은 **기본적으로 비활성화**되어 있으며, `config.json`에서 명시적으로 활성화해야 합니다:

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

**Android APK**: [GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest)에서
다운로드합니다. 설치 후 서버 주소와 `api_server` 사용자 이름/비밀번호를 입력하면
연결됩니다. 전체 설정, 리버스 프록시 및 보안 관련 안내:
[docs/ck_quant_mobile_admin.md](docs/ck_quant_mobile_admin.md).

**Telegram 봇**: 동일한 7개 로케일이 봇이 보내는 모든 메시지 — 주문 알림,
`/status`, `/profit`, `/balance`, 일간/주간/월간 리포트, 그리고 RPC 계층이 채팅에
보고하는 오류 — 를 지원합니다. 기본 언어는 `config.json`에서 지정합니다:

```json
"telegram": {
  "language": "zh-CN"
}
```

`/language`(별칭 `/lang`)는 실행 중에 개별 채팅의 언어를 전환하며, 선택 사항은
재시작 후에도 유지됩니다(`user_data/bot_languages.json`). 명령어 전체 목록과
참고 자료: [docs/telegram-usage.md](docs/telegram-usage.md).

### 2. 상승/하락 페어리스트 (변동률 순위)

상승 상위와 하락 상위를 동적으로 선택하며 **두 가지 모드**를 지원합니다:

- `filter`(기본값): 네이티브 freqtrade 체인 — 업스트림 페어리스트 범위 내에서만 순위 산정
- `union`: 전체 시장에서 독립적으로 선택하고 업스트림 결과와 **병합**
  (거래량 + 상승/하락 + 정적 리스트가 공존 가능)

```jsonc
"pairlists": [
    {
        "method": "VolumePairList",
        "number_assets": 20,
        "sort_key": "quoteVolume",
        "refresh_period": 300
    },
    {
        "method": "GainersLosersPairList",
        "gainers_count": 10,      // top 10 gainers
        "losers_count": 5,        // top 5 losers
        "direction": "both",      // both / gainers / losers
        "mode": "union",          // union (hybrid) or filter
        "refresh_period": 300
    }
]
```

검증 방법:

```bash
docker compose run --rm CK_Quant test-pairlist \
    --userdir user_data --config user_data/config.json
```

전체 레퍼런스: [docs/gainers-losers-pairlist.md](docs/gainers-losers-pairlist.md).

### 3. Tick 레벨 백테스트 엔진

실제 Tick 시퀀스로 청산을 매칭하여 OHLCV 백테스트의 정확도 문제를 해결합니다:

```text
Within one 15m bar both stop-loss and take-profit are hit — which came first?
  OHLCV backtest: guesses (assumed path) → systematically optimistic ❌
  Tick backtest:  real tick sequence → exact ✅
```

**실측**(ETH 2025-07, 0.5% 손절): 거래의 7.1%에서 트리거 주문 순서가 잘못
판정되었고, OHLCV 순손익 방향이 실제 Tick 결과와 반대였습니다. 손절 폭이
타이트할수록 오차가 커집니다.

```bash
# Download tick data (binance.vision, weekly chunks)
python scripts/download_vision_chunked.py ETHUSDT 20250701 20250731 \
    user_data/data/binance/futures/trades_eth

# Run the tick backtest
python -m freqtrade.ck_quant.tick_backtest \
    --config user_data/config.json --strategy MyPrivateStrategy \
    --data-dir user_data/data/binance/futures/trades_eth \
    --timerange 20250701-20250731 --pair "ETH/USDT:USDT" \
    --stoploss 0.005 --takeprofit 0.005
```

자세히: [docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md).

### 4. 합성 아이스버그 주문

대량 주문을 숨겨진 조각으로 분할하며, 거래소는 한 번에 하나의 조각만 보게 됩니다:

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

자세히: [docs/advanced-iceberg.md](docs/advanced-iceberg.md).

### 5. 원클릭 릴리스

```bash
python scripts/release.py 2026.8          # build → push Docker Hub → tag → GitHub Release
python scripts/release.py 2026.8 --dry-run  # preview
```

### 6. 공개 쇼케이스 페이지 (게스트 접근)

계정이 없는 방문자도 봇의 성과를 볼 수 있도록 읽기 전용, 집계 수치만 담은 개요를
선택적으로 공개할 수 있습니다. 기본적으로 꺼져 있습니다(비활성 상태에서는 공개
엔드포인트가 `404`를 반환합니다):

```json
{
    "api_server": {
        "public_showcase": {
            "enabled": true,
            "label": "Bot A",
            "show_absolute": true,
            "cache_ttl_secs": 30
        }
    }
}
```

메인 설정에 활성화하거나, 별도의 overlay 파일로 만들어 두 번째 `--config`로 추가하거나,
WebUI(**설정 → 게스트 공개 범위**)에서 활성화할 수 있습니다. WebUI에서는 여러 봇을
한 번에 볼 수 있는 공유 링크 `/showcase?api=…&api=…`도 생성됩니다. 방문자는 대시보드
첫 화면의 집계 수치만 볼 수 있으며 페어명, 전략명, 개별 거래 내역, 설정, 키는 절대
볼 수 없습니다. 다만 이 페이지는 **여전히 당신의 성과와 잔고를 공개**하므로 공유하기
전에 신중하게 판단하십시오.

자세히: [docs/ck-quant-public-showcase.md](docs/ck-quant-public-showcase.md).

---

## 백테스팅

```bash
docker compose run --rm CK_Quant backtesting \
    --userdir user_data \
    --config user_data/config.json \
    --strategy YourStrategy \
    --timeframe 15m --timeframe-detail 1m \
    --timerange 20260101-20260801 \
    --fee 0.001
```

> 신뢰할 수 있는 결과를 얻으려면 `--timeframe-detail 1m`을 사용하십시오 — 순수 15m
> 백테스트는 체계적으로 낙관적입니다(대규모 표본에서 약 12배 과대평가 실측).

---

## Freqtrade 업스트림

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade는 Python으로 작성된 무료 오픈 소스 암호화폐 트레이딩 봇입니다.
모든 주요 거래소를 지원하고 Telegram 또는 webUI로 제어하도록 설계되었습니다.
백테스팅, 플로팅, 자금 관리 도구는 물론 머신러닝을 통한 전략 최적화 기능도
포함합니다.

이 프로젝트는 Freqtrade에서 파생되었으며 GPL-3.0 라이선스를 유지합니다. 아키텍처
설명은 [CK_QUANT.md](CK_QUANT.md)를 참조하십시오.

## 면책 조항

이 소프트웨어는 교육 목적으로만 제공됩니다. 잃어도 괜찮지 않은 자금은 투입하지
마십시오. **본 소프트웨어 사용에 따른 위험은 전적으로 사용자 본인에게 있습니다.**
저자와 모든 관련자는 귀하의 거래 결과에 대해 어떠한 책임도 지지 않습니다.

항상 트레이딩 봇을 Dry-Run(모의 투자)으로 먼저 실행하고, 동작 원리와 예상 손익을
이해하기 전에는 실자금을 투입하지 마십시오.

코딩과 Python 지식이 있기를 강력히 권장합니다. 주저하지 말고 소스 코드를 읽고
이 봇의 메커니즘을 이해하십시오.

---

## 라이선스

GPL-3.0 — [LICENSE](LICENSE)를 참조하십시오.
