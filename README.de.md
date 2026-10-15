# CK Quant

**Eine datenschutzorientierte Freqtrade-Distribution mit Web- und Android-Fernverwaltung**

**[English](README.md) | [中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [日本語](README.ja.md) | [한국어](README.ko.md)**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## Funktionen

| Funktion | Beschreibung |
|---|---|
| **Absturzsichere Order-Wiederherstellung** | Stellt Exchange-Orders nach schnellem Stop-and-Reverse-Trading wieder her und verhindert Endlos-Neustartschleifen |
| **Synthetische Iceberg-Orders** | Optionales Aufteilen großer Orders in versteckte Teilscheiben für Einstiege und Ausstiege |
| **Kartenbasiertes responsives UI** | Halbtransparentes, mobilfreundliches WebUI mit 7 Sprachen (zh-CN, zh-TW, en, de, ja, fr, ko) |
| **Mehrsprachiger Bot** | Telegram-Benachrichtigungen, -Befehle und Chat-Fehler nutzen dieselben 7 Sprachen; Umschalten per `/language` |
| **Authentifizierter Admin-Arbeitsbereich** | Konfiguration und Strategie online bearbeiten/validieren, Auto-Backup, sicheres Reload/Restart |
| **Android-App** | Verbinde dich mit deinem Server, verwalte Bots und bediene Trades vom Handy aus |
| **CK Quant Desktop** | Einsteigerfreundlicher Windows-Arbeitsbereich mit offline-Lebenszeitlizenz pro Maschine, verschlüsselten Zugangsdaten, KI-Chat, seriellen Backtests, deterministischen G1-G10-Gates, Monitoring und bestätigtem Paper-Deployment |
| **Tick-genaue Backtest-Engine** | Speicherfreundliche Engine, die Ausstiege anhand echter Tick-Sequenzen matcht, statt OHLCV-Bar-Pfade zu raten |
| **Mark-to-Market-Drawdown** | Equity-Drawdown aus realisiertem und unrealisiertem P&L |
| **Gainers/Losers-Pairlist** | Rankt Paare nach prozentualer Veränderung (Top-Gewinner + Top-Verlierer), mischbar mit Volumen- oder statischen Listen |
| **Echtzeit-Profitfaktor** | Bezieht unrealisierten P&L offener Trades ein — die Statistik hinkt nie nach, während der Bot läuft |
| **Öffentliche Showcase-Seite** | Opt-in, schreibgeschützte öffentliche Übersicht (`/showcase`) für Besucher ohne Konto — nur aggregierte Zahlen, keine Paare, Strategienamen, Trades oder Keys |
| **Release mit einem Befehl** | Build → Push zu Docker Hub → Tag → GitHub Release in einem Befehl |
| **Alles schließen mit einem Klick** | WebUI-Button (Desktop + Mobil), der alle offenen Positionen der in der Liste gezeigten Bots schließt — mit zweiter Bestätigung, wenn Live-Bots betroffen sind |


---

## CK Quant Desktop

Die Windows-Desktop-App liegt unter [`desktop/`](desktop/). Sie verwendet eine einmalige, an einen Maschinencode gebundene **10.000-USDT-Lebenszeitlizenz**; ein wiederkehrendes Abo gibt es nicht. Die Kunden-App enthält nur den öffentlichen Verifikationsschlüssel, während Registrierungscodes in der separaten, von Git ignorierten Hersteller-Konsole signiert werden.

Der One-Click-Recherche-Workflow startet mit einer 15m-Anpassung von Freqtrades öffentlicher `SampleStrategy`, niemals mit der privaten Strategie eines Nutzers. Importierte private Strategien, generierte Varianten, API-Zugangsdaten, Backtest-Artefakte und Audit-Daten bleiben im lokalen Anwendungsdaten-Verzeichnis und sind von Git und Release-Paketen ausgeschlossen.

Alle Backtests laufen seriell über den lokalen CK-Quant-Docker-Container. Fehlende statistische Belege werden als **nicht bewertet** angezeigt, und ein Paper-Deployment erfordert eine ausdrückliche Bestätigung durch den Nutzer. Die Aktivierung von Live-Kapital bleibt ein separater manueller Bestätigungsschritt.

Details zu Installation, Aktivierung und Entwicklung findest du in [`desktop/README.md`](desktop/README.md).

---

## Installation (Docker)

**Voraussetzungen**: Docker mit Compose v2. Keine Python-Umgebung nötig.

```bash
mkdir CK_Quant
cd CK_Quant

# Compose-Datei herunterladen
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml

# Image pullen und dein Nutzerverzeichnis anlegen
docker compose pull
docker compose run --rm CK_Quant create-userdir --userdir user_data
> Der Compose-Service läuft mit `working_dir: /CK_Quant`, daher landen relative
> Pfade wie `user_data` im gemounteten Volume.
> (Ein absoluter Pfad funktioniert ebenfalls: `--userdir /CK_Quant/user_data`)


# Startkonfiguration erzeugen
docker compose run --rm CK_Quant new-config --config user_data/config.json
```

**Image-Auswahl**:

| Image | Anwendungsfall |
|---|---|
| `ericchenghz/ck-quant:stable` | Standardhandel (empfohlen) |
| `ericchenghz/ck-quant:stable-freqai` | FreqAI-Modelle (LightGBM/XGBoost/RF) |
| `ericchenghz/ck-quant:stable-freqai-rl` | FreqAI + PyTorch-Reinforcement-Learning |

Setze `CK_QUANT_IMAGE` in `.env`, um zu wechseln.

### Ersteinrichtung

Nach `new-config` bearbeitest du `user_data/config.json` und setzt die wichtigsten Werte:

```jsonc
{
    "exchange": {
        "name": "binance",
        "key": "YOUR_API_KEY",       // von der Exchange beziehen (Futures-Handel aktivieren)
        "secret": "YOUR_API_SECRET", // geheim halten — gelangt nie ins Image
        "pair_whitelist": ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    },
    "stake_amount": 100,             // fester Betrag pro Trade
    "max_open_trades": 5,
    "dry_run": true                  // im Paper-Trading-Modus starten!
}
```

> **Starte immer mit `dry_run: true`** (Paper-Trading). Wechsle erst auf
> `false`, nachdem du das Verhalten des Bots und den erwarteten P&L verstanden hast.
> Für Futures erstelle API-Keys mit gesetztem Häkchen bei **Enable Futures**.

### Strategie einbinden und starten

```bash
# 1. Kopiere deine private Strategie nach user_data/strategies/
# 2. Kopiere .env.example nach .env und setze CK_QUANT_STRATEGY auf deinen Klassennamen
cp .env.example .env
#    CK_QUANT_STRATEGY=YourStrategyName

# 3. Starten
docker compose up -d
docker compose logs -f --tail 200
```

Das WebUI lauscht standardmäßig auf <http://127.0.0.1:8080> (konfigurierbar über `CK_QUANT_WEBUI_BIND` / `CK_QUANT_WEBUI_PORT`).

Konfiguration, Strategien, Datenbank, Zugangsdaten, Modelle und Logs liegen alle im
lokalen `user_data`-Verzeichnis — **nichts Sensibles gelangt ins Image**.

> **Sicherheit**: Gib den Admin-/API-Port niemals ins öffentliche Internet frei.
> Nutze einen HTTPS-Reverse-Proxy oder ein vertrauenswürdiges VPN sowie ein starkes,
> einzigartiges Passwort und ein JWT-Secret. Teste zuerst gegen eine `dry_run`-Instanz.

---

## Funktionsanleitungen

### 1. Mehrsprachiges WebUI und Android-App

Das WebUI liefert 7 Sprachen und einen authentifizierten Admin-Arbeitsbereich:

- Gängige oder vollständige Konfigurationsparameter bearbeiten, mit serverseitiger Validierung vor dem Speichern
- Strategieparameter oder Strategiedateien online bearbeiten
- Automatische Backups von Config und Strategie, sicheres Reload oder Restart nach dem Speichern
- Laufzeitstatus ansehen, Orders und Positionen über die Freqtrade-API verwalten
- Den Admin-Audit-Trail einsehen

Admin ist **standardmäßig deaktiviert**; aktiviere es ausdrücklich in `config.json`:

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

**Android-APK**: Download über
[GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest).
Nach der Installation gibst du deine Serveradresse sowie Benutzername und Passwort des `api_server` ein.
Vollständige Einrichtung, Reverse-Proxy- und Sicherheitshinweise:
[docs/ck_quant_mobile_admin.md](docs/ck_quant_mobile_admin.md).

**Telegram-Bot**: Dieselben 7 Sprachen decken jede Nachricht ab, die der Bot sendet —
Order-Benachrichtigungen, `/status`, `/profit`, `/balance`, die Tages-, Wochen- und
Monatsreports sowie die Fehler, die die RPC-Schicht im Chat meldet. Die
Standardsprache wählst du in `config.json`:

```json
"telegram": {
  "language": "zh-CN"
}
```

`/language` (Alias `/lang`) schaltet die Sprache eines einzelnen Chats zur Laufzeit um,
und die Auswahl übersteht Neustarts (`user_data/bot_languages.json`). Referenz und
die vollständige Befehlsliste: [docs/telegram-usage.md](docs/telegram-usage.md).

### 2. Gainers/Losers-Pairlist (Ranking nach prozentualer Veränderung)

Wähle dynamisch die Top-Gewinner und Top-Verlierer, mit **zwei Modi**:

- `filter` (Standard): native Freqtrade-Kette — rankt nur innerhalb der vorgelagerten Pairlist
- `union`: wählt unabhängig aus dem gesamten Markt und **führt** die Ergebnisse mit der
  vorgelagerten Liste **zusammen** (Volume + Gainers + Static können koexistieren)

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
        "gainers_count": 10,      // Top 10 Gewinner
        "losers_count": 5,        // Top 5 Verlierer
        "direction": "both",      // both / gainers / losers
        "mode": "union",          // union (hybrid) oder filter
        "refresh_period": 300
    }
]
```

Prüfen mit:

```bash
docker compose run --rm CK_Quant test-pairlist \
    --userdir user_data --config user_data/config.json
```

Vollständige Referenz: [docs/gainers-losers-pairlist.md](docs/gainers-losers-pairlist.md).

### 3. Tick-genaue Backtest-Engine

Mische Ausstiege anhand echter Tick-Sequenzen, um die Genauigkeit des OHLCV-Backtests zu korrigieren:

```text
Innerhalb einer 15m-Bar werden sowohl Stop-Loss als auch Take-Profit getroffen — was kam zuerst?
  OHLCV-Backtest: rät (angenommener Pfad) → systematisch optimistisch ❌
  Tick-Backtest:  echte Tick-Sequenz → exakt ✅
```

Gemessen (ETH 2025-07, 0,5 % Stop): Bei 7,1 % der Trades wurde die Trigger-Order
falsch beurteilt, und die Richtung des OHLCV-Netto-P&L war der des echten Tick-Ergebnisses
entgegengesetzt. Engere Stops → größerer Fehler.

```bash
# Tick-Daten herunterladen (binance.vision, wochenweise Blöcke)
python scripts/download_vision_chunked.py ETHUSDT 20250701 20250731 \
    user_data/data/binance/futures/trades_eth

# Tick-Backtest ausführen
python -m freqtrade.ck_quant.tick_backtest \
    --config user_data/config.json --strategy MyPrivateStrategy \
    --data-dir user_data/data/binance/futures/trades_eth \
    --timerange 20250701-20250731 --pair "ETH/USDT:USDT" \
    --stoploss 0.005 --takeprofit 0.005
```

Details: [docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md).

### 4. Synthetische Iceberg-Orders

Teile eine große Order in versteckte Teilscheiben auf; die Exchange sieht immer nur eine davon:

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

Details: [docs/advanced-iceberg.md](docs/advanced-iceberg.md).

### 5. Release mit einem Befehl

```bash
python scripts/release.py 2026.8          # Build → Push zu Docker Hub → Tag → GitHub Release
python scripts/release.py 2026.8 --dry-run  # Vorschau
```

### 6. Öffentliche Showcase-Seite (Gastzugriff)

Optional veröffentlichst du eine schreibgeschützte, nur aus aggregierten Zahlen bestehende Übersicht,
damit Besucher ohne Konto sehen, wie ein Bot abschneidet. Standardmäßig aus (der öffentliche Endpunkt antwortet `404`, solange sie deaktiviert ist):

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

Aktiviere sie in der Hauptkonfiguration, als separate Overlay-Datei, die mit einem zweiten `--config`
ergänzt wird, oder im WebUI (**Einstellungen → Gastsichtbarkeit**), das zusätzlich einen teilbaren
`/showcase?api=…&api=…`-Link für mehrere Bots erzeugt. Besucher sehen immer nur die aggregierten
Zahlen des Dashboards auf dem ersten Bildschirm — niemals Pair-Namen, Strategienamen, Trade-Zeilen,
Config oder Keys — die Seite veröffentlicht aber weiterhin deine Performance und dein Guthaben, entscheide also bewusst, bevor du sie teilst.

Details: [docs/ck-quant-public-showcase.md](docs/ck-quant-public-showcase.md).

---

## Backtesting

```bash
docker compose run --rm CK_Quant backtesting \
    --userdir user_data \
    --config user_data/config.json \
    --strategy YourStrategy \
    --timeframe 15m --timeframe-detail 1m \
    --timerange 20260101-20260801 \
    --fee 0.001
```

> Verwende `--timeframe-detail 1m` für verlässliche Ergebnisse — reine 15m-Backtests sind
> systematisch optimistisch (gemessen: 12-fache Überzeichnung bei großer Stichprobe).

---

## Freqtrade-Upstream

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade ist ein freier und quelloffener Krypto-Trading-Bot, geschrieben in Python.
Er ist darauf ausgelegt, alle großen Exchanges zu unterstützen, und wird über Telegram
oder WebUI gesteuert. Er enthält Werkzeuge für Backtesting, Plotting und Money-Management
sowie Strategieoptimierung durch maschinelles Lernen.

Dieses Projekt ist von Freqtrade abgeleitet und bleibt unter GPL-3.0 lizenziert. Architekturhinweise
findest du in [CK_QUANT.md](CK_QUANT.md).

## Haftungsausschluss

Diese Software dient ausschließlich Lehr- und Bildungszwecken. Setze kein Geld
aufs Spiel, dessen Verlust du nicht verkraften würdest. NUTZUNG AUF EIGENES RISIKO.
DIE AUTOREN UND ALLE VERBUNDENEN PARTEIEN ÜBERNEHMEN KEINE VERANTWORTUNG FÜR DEINE TRADING-ERGEBNISSE.

Beginne immer damit, den Trading-Bot im Dry-Run zu betreiben, und setze kein Geld ein,
bevor du verstehst, wie er funktioniert und welchen Gewinn bzw. Verlust du
erwarten solltest.

Wir empfehlen dir dringend, Programmier- und Python-Kenntnisse mitzubringen. Scheue dich nicht,
den Quellcode zu lesen und den Mechanismus dieses Bots zu verstehen.

---

## Lizenz

GPL-3.0 — siehe [LICENSE](LICENSE).
