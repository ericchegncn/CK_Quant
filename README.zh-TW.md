# CK Quant

**隱私優先、內建網頁與 Android 遠端管理的 Freqtrade 二次發行版**

**[English](README.md) | [中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [日本語](README.ja.md) | [한국어](README.ko.md)**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## 功能特色

| 功能 | 說明 |
|---|---|
| **當機安全的訂單復原** | 在快速平倉反手交易後還原交易所訂單，避免無限重啟迴圈 |
| **合成冰山單** | 可選擇將大筆訂單拆成隱藏的批次，用於進場與出場 |
| **卡片式響應式 UI** | 半透明、適合行動裝置的 WebUI，支援 7 種語言（zh-CN、zh-TW、en、de、ja、fr、ko） |
| **多語言機器人** | Telegram 通知、指令與聊天室錯誤訊息使用同樣的 7 種語言；可用 `/language` 切換單一聊天室 |
| **具備驗證的管理工作區** | 線上編輯與驗證設定和策略、自動備份、安全重新載入／重啟 |
| **Android App** | 連線到你的伺服器、管理機器人、用手機操作交易 |
| **CK Quant 桌面版** | 面向新手的 Windows 工作區，具備離線終身機器授權、加密憑證、AI 對話、序列回測、確定性的 G1-G10 關卡、監控，以及經確認的模擬盤部署 |
| **Tick 級回測引擎** | 記憶體友善的引擎，依真實逐筆成交序列媒合出場，而不是猜測 OHLCV K 線路徑 |
| **市價計價回撤** | 權益回撤同時納入已實現與未實現損益 |
| **漲幅／跌幅交易對清單** | 依漲跌幅排序交易對（漲幅榜 + 跌幅榜），可與成交量／靜態清單混合使用 |
| **即時獲利因子** | 納入未平倉交易的未實現損益 —— 機器人運行期間統計數字不會落後 |
| **公開展示頁** | 可選擇開啟的唯讀公開總覽（`/showcase`），讓沒有帳號的訪客也能瀏覽 —— 僅提供彙總數字，不含交易對、策略名稱、交易明細或金鑰 |
| **一行指令發布** | 一行指令完成 建置 → 推送 Docker Hub → 打標籤 → GitHub Release |
| **一鍵全部平倉** | WebUI 按鈕（桌面 + 手機）平掉清單中顯示的那些 bot 的全部部位；含實盤 bot 時追加第二次確認 |


---

## CK Quant 桌面版

Windows 桌面應用程式位於 [`desktop/`](desktop/)。它採用一次付清的 **10,000 USDT 終身授權**，並綁定機器碼；沒有週期性訂閱。客戶端應用程式只包含公開的驗簽金鑰，而註冊碼則由另一個獨立、被 Git 忽略的廠商主控台簽發。

一鍵研究流程以 Freqtrade 官方公開的 `SampleStrategy` 之 15m 改編版為起點，絕不從使用者的私人策略出發。匯入的私人策略、產生的變體、API 憑證、回測產物與稽核資料都留在本機應用程式資料目錄，並被排除在 Git 與發行套件之外。

所有回測都透過本機 CK Quant Docker 容器序列執行。缺少統計證據時會顯示為**尚未評估**，而模擬盤部署需要使用者明確確認。實盤資金啟用仍保留為獨立的手動確認步驟。

安裝、啟用與開發細節請見 [`desktop/README.md`](desktop/README.md)。

---

## 安裝（Docker）

**先決條件**：具備 Compose v2 的 Docker。不需要 Python 環境。

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

**映像選擇**：

| 映像 | 使用情境 |
|---|---|
| `ericchenghz/ck-quant:stable` | 標準交易（建議） |
| `ericchenghz/ck-quant:stable-freqai` | FreqAI 模型（LightGBM/XGBoost/RF） |
| `ericchenghz/ck-quant:stable-freqai-rl` | FreqAI + PyTorch 強化學習 |

在 `.env` 中設定 `CK_QUANT_IMAGE` 即可切換。

### 首次設定

執行 `new-config` 之後，編輯 `user_data/config.json` 設定必要項目：

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

> **務必以 `dry_run: true` 開始**（模擬盤交易）。只有在理解機器人的行為與
> 預期損益之後，才切換為 `false`。若交易合約，建立 API 金鑰時請勾選
> **Enable Futures**。

### 放入你的策略並啟動

```bash
# 1. Copy your private strategy into user_data/strategies/
# 2. Copy .env.example to .env and set CK_QUANT_STRATEGY to your class name
cp .env.example .env
#    CK_QUANT_STRATEGY=YourStrategyName

# 3. Start
docker compose up -d
docker compose logs -f --tail 200
```

WebUI 預設監聽 <http://127.0.0.1:8080>（可透過 `CK_QUANT_WEBUI_BIND` / `CK_QUANT_WEBUI_PORT` 設定）。

設定、策略、資料庫、憑證、模型與日誌全部存放在本機的 `user_data` 目錄 ——
**任何敏感資料都不會進入映像檔**。

> **安全性**：切勿將管理／API 連接埠暴露到公開網際網路。
> 請使用 HTTPS 反向代理或可信任的 VPN，並搭配高強度且唯一的密碼
> 與 JWT 金鑰。請先在 `dry_run` 執行個體上測試。

---

## 功能指南

### 1. 多語言 WebUI 與 Android App

WebUI 內建 7 種語言與具備驗證的管理工作區：

- 編輯常用或完整設定參數，儲存前由伺服器端驗證
- 線上編輯策略參數或策略檔案
- 自動備份設定／策略，儲存後安全重新載入或重啟
- 檢視執行狀態，透過 Freqtrade API 管理訂單與持倉
- 檢視管理員稽核軌跡

管理功能**預設為停用**；請在 `config.json` 中明確啟用：

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

**Android APK**：請從
[GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest)
下載。安裝後輸入你的伺服器位址以及 `api_server` 使用者名稱／密碼。
完整設定、反向代理與安全性說明：
[docs/ck_quant_mobile_admin.md](docs/ck_quant_mobile_admin.md)。

**Telegram 機器人**：同樣的 7 種語言涵蓋機器人送出的每一則訊息 —— 訂單
通知、`/status`、`/profit`、`/balance`、每日／每週／每月
報表，以及 RPC 層在聊天室回報的錯誤。在 `config.json` 中選擇預設
語言：

```json
"telegram": {
  "language": "zh-CN"
}
```

`/language`（別名 `/lang`）可在執行期間切換單一聊天室的語言，
且該選擇在重啟後依然保留（`user_data/bot_languages.json`）。參考資料與
完整指令清單：[docs/telegram-usage.md](docs/telegram-usage.md)。

### 2. 漲幅／跌幅交易對清單（依漲跌幅排序）

動態選出漲幅榜與跌幅榜前段班，具備**兩種模式**：

- `filter`（預設）：原生 freqtrade 鏈 —— 僅在上游交易對清單內排序
- `union`：從整個市場獨立挑選，並與上游**合併**
  （成交量 + 漲跌幅 + 靜態清單可並存）

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

驗證方式：

```bash
docker compose run --rm CK_Quant test-pairlist \
    --userdir user_data --config user_data/config.json
```

完整參考：[docs/gainers-losers-pairlist.md](docs/gainers-losers-pairlist.md)。

### 3. Tick 級回測引擎

依真實逐筆成交序列媒合出場，修正 OHLCV 回測的準確度：

```text
Within one 15m bar both stop-loss and take-profit are hit — which came first?
  OHLCV backtest: guesses (assumed path) → systematically optimistic ❌
  Tick backtest:  real tick sequence → exact ✅
```

實測（ETH 2025-07，0.5% 停損）：7.1% 的交易其觸發順序被誤判，
且 OHLCV 淨損益方向與真實逐筆結果相反。停損越緊，誤差越大。

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

細節：[docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md)。

### 4. 合成冰山單

將一筆大單拆成隱藏的批次；交易所同一時間只會看到其中一批：

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

細節：[docs/advanced-iceberg.md](docs/advanced-iceberg.md)。

### 5. 一行指令發布

```bash
python scripts/release.py 2026.8          # build → push Docker Hub → tag → GitHub Release
python scripts/release.py 2026.8 --dry-run  # preview
```

### 6. 公開展示頁（訪客存取）

可選擇發布只讀、僅含彙總資訊的總覽，讓沒有帳號的訪客也能看到
機器人的表現。此功能預設為停用（停用期間公開端點回應 `404`）：

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

你可以在主設定檔中啟用、以第二個 `--config` 加入獨立的 overlay 檔案，
或直接在 WebUI 中啟用（**設定 → 訪客可見性**），後者同時會產生可分享的
`/showcase?api=…&api=…` 連結，供多個機器人使用。訪客只會看到儀表板首屏的
彙總數字 —— 絕不會看到交易對名稱、策略名稱、交易明細、設定或金鑰 —— 但該頁面
仍會公開你的績效與餘額，因此分享前請審慎決定。

細節：[docs/ck-quant-public-showcase.md](docs/ck-quant-public-showcase.md)。

---

## 回測

```bash
docker compose run --rm CK_Quant backtesting \
    --userdir user_data \
    --config user_data/config.json \
    --strategy YourStrategy \
    --timeframe 15m --timeframe-detail 1m \
    --timerange 20260101-20260801 \
    --fee 0.001
```

> 請使用 `--timeframe-detail 1m` 以獲得可靠結果 —— 純 15m 回測會
> 系統性偏向樂觀（在大樣本上實測高估 12 倍）。

---

## Freqtrade 上游專案

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade 是一套以 Python 撰寫的免費開源加密貨幣交易機器人。
它的設計支援所有主要交易所，並可透過 Telegram 或 webUI 控制。
它內含回測、繪圖與資金管理工具，以及透過機器學習進行的
策略最佳化。

本專案衍生自 Freqtrade，並維持 GPL-3.0 授權。架構說明請見
[CK_QUANT.md](CK_QUANT.md)。

## 免責聲明

本軟體僅供教育用途。請勿投入你害怕失去的資金。**使用本軟體風險自負**。
作者及所有關係企業對你的交易結果不承擔任何責任。

請務必先以 Dry-Run（模擬盤）執行交易機器人，並且在你了解其運作方式
以及應預期的獲利／虧損之前，不要投入資金。

我們強烈建議你具備程式設計與 Python 知識。請不要
猶豫去閱讀原始碼，並理解這隻機器人的運作機制。

---

## 授權條款

GPL-3.0 — 見 [LICENSE](LICENSE)。
