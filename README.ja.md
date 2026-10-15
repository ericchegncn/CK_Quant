# CK Quant

**プライバシー重視の Freqtrade ディストリビューション — Web と Android による遠隔管理**

**[English](README.md) | [中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [日本語](README.ja.md) | [한국어](README.ko.md)**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## 機能

| 機能 | 説明 |
|---|---|
| **クラッシュセーフな注文復旧** | 急激なドテン売買の後に取引所の注文を復元し、無限の再起動ループを防ぐ |
| **合成アイスバーグ注文** | 大きな注文を任意で隠れた小口に分割（エントリーとエグジットの両方） |
| **カード型レスポンシブ UI** | 半透明でモバイルに優しい WebUI。7 言語（zh-CN、zh-TW、en、de、ja、fr、ko）に対応 |
| **多言語ボット** | Telegram の通知・コマンド・チャット上のエラーが同じ 7 言語に対応。`/language` でチャットごとに切り替え |
| **認証付きの管理ワークスペース** | 設定と戦略をオンラインで編集・検証、自動バックアップ、安全なリロード／再起動 |
| **Android アプリ** | サーバーに接続し、スマホからボットの管理と取引の操作が可能 |
| **CK Quant Desktop** | 初心者向けの Windows ワークスペース。オフラインの永久マシンライセンス、資格情報の暗号化、AI チャット、直列バックテスト、決定論的な G1-G10 ゲート、監視、確認済みのペーパー配備 |
| **Tick レベルのバックテストエンジン** | メモリに優しいエンジン。OHLCV バーの値動きを推測せず、実際の tick シーケンスでイグジットを約定 |
| **時価評価ベースのドローダウン** | 確定損益と含み損益を合算したエクイティのドローダウン |
| **上昇率／下落率ペアリスト** | 変化率でペアを順位付け（上昇上位 + 下落上位）。出来高リストや静的リストと混在可能 |
| **リアルタイムのプロフィットファクター** | 保有中ポジションの含み損益を算入 —— ボット稼働中も統計が遅れない |
| **公開ショーケースページ** | オプトインの読み取り専用・公開概要（`/showcase`）。アカウントのない訪問者向けで集計値のみ。ペア、戦略名、取引、キーは含まない |
| **ワンコマンドリリース** | 1 つのコマンドで ビルド → Docker Hub へ push → タグ付け → GitHub Release |
| **ワンクリック全決済** | 一覧に表示されている bot の全ポジションをまとめて決済する WebUI ボタン（PC・スマホ対応）。LIVE の bot が含まれる場合は二重確認 |


---

## CK Quant Desktop

Windows デスクトップアプリは [`desktop/`](desktop/) にあります。マシンコードに紐づく**10,000 USDT の買い切り（生涯）ライセンス**を一度だけ購入する方式で、継続課金はありません。顧客向けアプリには公開された検証鍵のみが含まれ、登録コードは別個の（Git 管理外の）メーカーコンソールで署名されます。

ワンクリックのリサーチワークフローは、Freqtrade 公式の公開 `SampleStrategy` を 15m 用に適合させたものから出発し、ユーザーの非公開戦略から始めることはありません。インポートした非公開戦略、生成されたバリアント、API 資格情報、バックテスト成果物、監査データはすべてローカルのアプリケーションデータディレクトリに留まり、Git およびリリースパッケージから除外されます。

すべてのバックテストはローカルの CK Quant Docker コンテナを通じて直列に実行されます。統計的根拠が不足している項目は **未評価** と表示され、ペーパー配備にはユーザーによる明示的な確認が必要です。実資金の稼働開始は、引き続き別途の手動確認ステップです。

インストール・アクティベーション・開発の詳細は [`desktop/README.md`](desktop/README.md) を参照してください。

---

## インストール（Docker）

**前提条件**: Docker（Compose v2 を含む）。Python 環境は不要です。

```bash
mkdir CK_Quant
cd CK_Quant

# compose ファイルをダウンロード
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml

# イメージを取得し、ユーザーディレクトリを作成
docker compose pull
docker compose run --rm CK_Quant create-userdir --userdir user_data
> The compose service runs with `working_dir: /CK_Quant`, so relative
> paths like `user_data` land inside the mounted volume.
> (Absolute path also works: `--userdir /CK_Quant/user_data`)


# スターター設定を生成
docker compose run --rm CK_Quant new-config --config user_data/config.json
```

**イメージの選択**:

| イメージ | 用途 |
|---|---|
| `ericchenghz/ck-quant:stable` | 通常のトレード（推奨） |
| `ericchenghz/ck-quant:stable-freqai` | FreqAI モデル（LightGBM/XGBoost/RF） |
| `ericchenghz/ck-quant:stable-freqai-rl` | FreqAI + PyTorch 強化学習 |

`.env` に `CK_QUANT_IMAGE` を設定して切り替えます。

### 初回設定

`new-config` の実行後、`user_data/config.json` を編集して必須項目を設定します:

```jsonc
{
    "exchange": {
        "name": "binance",
        "key": "YOUR_API_KEY",       // 取引所で取得（先物取引を有効化）
        "secret": "YOUR_API_SECRET", // 厳重に保管 —— イメージには入りません
        "pair_whitelist": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    },
    "stake_amount": 100,             // 取引ごとの固定額
    "max_open_trades": 5,
    "dry_run": true                  // まずペーパートレードで開始！
}
```

> **必ず `dry_run: true`（ペーパートレード）から始めてください。** ボットの
> 挙動と想定される損益を理解してから `false` に切り替えます。
> 先物の場合は、API キー作成時に **Enable Futures** をチェックしてください。

### 戦略を配置して起動する

```bash
# 1. 非公開戦略を user_data/strategies/ にコピー
# 2. .env.example を .env にコピーし、CK_QUANT_STRATEGY にクラス名を設定
cp .env.example .env
#    CK_QUANT_STRATEGY=YourStrategyName

# 3. 起動
docker compose up -d
docker compose logs -f --tail 200
```

WebUI は既定で <http://127.0.0.1:8080> を待ち受けます（`CK_QUANT_WEBUI_BIND` / `CK_QUANT_WEBUI_PORT` で変更可能）。

設定・戦略・データベース・資格情報・モデル・ログはすべてローカルの `user_data`
ディレクトリに置かれます —— **機密情報がイメージに入ることはありません**。

> **セキュリティ**: 管理／API ポートをインターネットに公開しないでください。
> HTTPS リバースプロキシまたは信頼できる VPN を使い、強力で固有のパスワードと
> JWT シークレットを設定してください。まず `dry_run` インスタンスで検証しましょう。

---

## 機能ガイド

### 1. 多言語 WebUI と Android アプリ

WebUI には 7 言語と、認証付きの管理ワークスペースが用意されています:

- 保存前のサーバー側検証つきで、よく使う設定項目または設定全体を編集
- 戦略パラメータまたは戦略ファイルをオンラインで編集
- 設定／戦略の自動バックアップ、保存後の安全なリロードまたは再起動
- Freqtrade API 経由で実行状態を確認し、注文とポジションを管理
- 管理者の監査証跡を確認

管理機能は**既定で無効**です。`config.json` で明示的に有効化します:

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

**Android APK**: [GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest)
からダウンロードできます。インストール後、サーバーアドレスと `api_server` の
ユーザー名／パスワードを入力します。セットアップの全体像、リバースプロキシと
セキュリティの注意点は
[docs/ck_quant_mobile_admin.md](docs/ck_quant_mobile_admin.md) を参照してください。

**Telegram ボット**: 同じ 7 言語が、ボットが送るあらゆるメッセージをカバーします ——
注文通知、`/status`、`/profit`、`/balance`、日次・週次・月次のレポート、
そして RPC レイヤーがチャットに報告するエラーまで。既定の言語は
`config.json` で設定します:

```json
"telegram": {
  "language": "zh-CN"
}
```

`/language`（別名 `/lang`）は実行中に単一チャットの言語を切り替え、その選択は
再起動後も保持されます（`user_data/bot_languages.json`）。リファレンスと
コマンドの全一覧: [docs/telegram-usage.md](docs/telegram-usage.md)。

### 2. 上昇率／下落率ペアリスト（変化率でランキング）

上昇率の上位と下落率の上位を動的に選択します。**2 つのモード**があります:

- `filter`（既定）: freqtrade ネイティブのチェーン —— 上流のペアリスト内でのみ順位付け
- `union`: 市場全体から独立に選択し、上流と**マージ**（出来高 + 上昇率 + 静的が共存可能）

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
        "gainers_count": 10,      // 上昇上位 10
        "losers_count": 5,        // 下落上位 5
        "direction": "both",      // both / gainers / losers
        "mode": "union",          // union（ハイブリッド）または filter
        "refresh_period": 300
    }
]
```

検証するには:

```bash
docker compose run --rm CK_Quant test-pairlist \
    --userdir user_data --config user_data/config.json
```

完全なリファレンス: [docs/gainers-losers-pairlist.md](docs/gainers-losers-pairlist.md)。

### 3. Tick レベルのバックテストエンジン

実際の tick シーケンスでイグジットを約定させ、OHLCV バックテストの精度問題を解決します:

```text
1 本の 15m バーの中で損切りと利確の両方に到達 —— どちらが先に来たか？
  OHLCV バックテスト: 推測（仮定した値動き）→ 系統的に楽観的 ❌
  Tick バックテスト:  実際の tick シーケンス → 正確 ✅
```

実測（ETH 2025-07、0.5% ストップ）: 取引の 7.1% でトリガー注文が
誤判定され、OHLCV の純損益の方向が実際の tick の結果と逆でした。
ストップを厳しくするほど誤差は大きくなります。

```bash
# tick データをダウンロード（binance.vision、週単位のチャンク）
python scripts/download_vision_chunked.py ETHUSDT 20250701 20250731 \
    user_data/data/binance/futures/trades_eth

# tick バックテストを実行
python -m freqtrade.ck_quant.tick_backtest \
    --config user_data/config.json --strategy MyPrivateStrategy \
    --data-dir user_data/data/binance/futures/trades_eth \
    --timerange 20250701-20250731 --pair "ETH/USDT:USDT" \
    --stoploss 0.005 --takeprofit 0.005
```

詳細: [docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md)。

### 4. 合成アイスバーグ注文

大きな注文を隠れた小口に分割。取引所が同時に見るのは常に 1 つだけです:

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

詳細: [docs/advanced-iceberg.md](docs/advanced-iceberg.md)。

### 5. ワンコマンドリリース

```bash
python scripts/release.py 2026.8          # ビルド → Docker Hub へ push → タグ付け → GitHub Release
python scripts/release.py 2026.8 --dry-run  # プレビュー
```

### 6. 公開ショーケースページ（ゲストアクセス）

アカウントを持たない訪問者がボットの運用状況を見られるよう、読み取り専用で
集計値のみの概要を任意で公開できます。既定では無効です（無効中は公開エンドポイントが `404` を返します）:

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

メイン設定に記述する、2 つ目の `--config` で追加する別のオーバーレイファイルとして用意する、
あるいは WebUI（**Settings → Guest visibility**）から有効化します。WebUI では複数のボットを
まとめて共有できる `/showcase?api=…&api=…` リンクも生成されます。訪問者が見られるのは
ダッシュボードの集計済みファーストスクリーン数値のみで、ペア名・戦略名・取引行・設定・キーは
決して表示されません —— ただしこのページは運用成績と残高を公開するため、共有前に意図的に判断してください。

詳細: [docs/ck-quant-public-showcase.md](docs/ck-quant-public-showcase.md)。

---

## バックテスト

```bash
docker compose run --rm CK_Quant backtesting \
    --userdir user_data \
    --config user_data/config.json \
    --strategy YourStrategy \
    --timeframe 15m --timeframe-detail 1m \
    --timerange 20260101-20260801 \
    --fee 0.001
```

> 信頼できる結果を得るには `--timeframe-detail 1m` を使ってください —— 純粋な
> 15m のバックテストは系統的に楽観的です（大規模サンプルで 12 倍の過大評価を実測）。

---

## Freqtrade アップストリーム

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade は Python で書かれた無料のオープンソース暗号資産トレーディングボットです。
主要な取引所すべてをサポートし、Telegram または webUI から操作できるよう
設計されています。バックテスト、プロット、資金管理のツールに加え、
機械学習による戦略最適化も備えています。

本プロジェクトは Freqtrade から派生したもので、引き続き GPL-3.0 で
ライセンスされています。アーキテクチャのメモは
[CK_QUANT.md](CK_QUANT.md) を参照してください。

## 免責事項

本ソフトウェアは教育目的のみを意図しています。失っても構わないと
思える資金だけを投入してください。本ソフトウェアは**自己責任で使用する**
ものであり、作者およびすべての関連者は、あなたの取引結果について
一切の責任を負いません。

必ず Dry-Run でトレーディングボットを動かすことから始め、その仕組みと
どの程度の損益を想定すべきかを理解する前に資金を投入しないでください。

コーディングと Python の知識を持つことを強く推奨します。ソースコードを
読み、このボットの仕組みを理解することをためらわないでください。

---

## ライセンス

GPL-3.0 — 詳細は [LICENSE](LICENSE) を参照してください。
