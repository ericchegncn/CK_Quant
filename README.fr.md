# CK Quant

**Une distribution Freqtrade axée sur la confidentialité, avec gestion à distance via le Web et Android**

**[English](README.md) | [中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [Deutsch](README.de.md) | [Français](README.fr.md) | [日本語](README.ja.md) | [한국어](README.ko.md)**

[![GitHub Release](https://img.shields.io/github/v/release/ericchegncn/CK_Quant?display_name=tag)](https://github.com/ericchegncn/CK_Quant/releases/latest)
[![Docker Hub](https://img.shields.io/docker/v/ericchenghz/ck-quant?label=Docker%20Hub&sort=semver)](https://hub.docker.com/r/ericchenghz/ck-quant/tags)
[![Android APK](https://img.shields.io/badge/Android-APK-3DDC84?logo=android&logoColor=white)](https://github.com/ericchegncn/CK_Quant/releases/latest)

---

## Fonctionnalités

| Fonctionnalité | Description |
|---|---|
| **Récupération d'ordres après crash** | Restaure les ordres auprès de l'exchange après des enchaînements rapides d'arrêt et d'inversion de position, empêchant les boucles de redémarrage infinies |
| **Ordres iceberg synthétiques** | Fractionnement optionnel des ordres importants en tranches masquées, à l'entrée comme à la sortie |
| **Interface réactive en cartes** | WebUI translucide et adaptée au mobile, avec 7 langues (zh-CN, zh-TW, en, de, ja, fr, ko) |
| **Bot multilingue** | Notifications, commandes et erreurs de chat Telegram dans les mêmes 7 langues ; changez la langue d'une conversation avec `/language` |
| **Espace d'administration authentifié** | Édition/validation en ligne de la configuration et de la stratégie, sauvegarde automatique, rechargement/redémarrage sûr |
| **Application Android** | Connectez-vous à votre serveur, gérez les bots, passez des ordres depuis votre téléphone |
| **CK Quant Desktop** | Espace de travail Windows pensé pour les débutants : licence à vie liée au code machine, identifiants chiffrés, chat IA, backtests séquentiels, garde-fous déterministes G1-G10, supervision et déploiement en paper trading confirmé |
| **Moteur de backtest au tick** | Moteur économe en mémoire qui apparie les sorties sur de vraies séquences de ticks au lieu de deviner le chemin des bougies OHLCV |
| **Drawdown mark-to-market** | Drawdown des capitaux propres combinant le P&L réalisé et le P&L non réalisé |
| **Pairlist Gainers/Losers** | Classe les paires par variation en pourcentage (plus fortes hausses + plus fortes baisses), mixable avec les listes volume/statiques |
| **Profit factor en temps réel** | Inclut le P&L non réalisé des positions ouvertes — les statistiques ne prennent jamais de retard pendant l'exécution du bot |
| **Page de vitrine publique** | Aperçu public en lecture seule et sur activation (`/showcase`) pour les visiteurs sans compte — chiffres agrégés uniquement, sans paires, noms de stratégies, transactions ni clés |
| **Publication en une commande** | Build → push Docker Hub → tag → GitHub Release en une seule commande |
| **Clôture totale en un clic** | Bouton WebUI (ordinateur + mobile) qui ferme toutes les positions ouvertes des bots affichés dans la liste, avec une seconde confirmation si des bots live sont concernés |


---

## CK Quant Desktop

L'application de bureau Windows se trouve dans [`desktop/`](desktop/). Elle repose sur une **licence à vie de 10 000 USDT** payée une seule fois et liée à un code machine ; aucun abonnement récurrent. L'application cliente ne contient que la clé publique de vérification, tandis que les codes d'enregistrement sont signés dans la console du fabricant, séparée et exclue de Git.

Le flux de recherche en un clic part d'une adaptation en 15m de la `SampleStrategy` publique de Freqtrade, jamais de la stratégie privée d'un utilisateur. Les stratégies privées importées, les variantes générées, les identifiants d'API, les artefacts de backtest et les données d'audit restent dans le répertoire local de données applicatives et sont exclus de Git et des paquets de publication.

Tous les backtests s'exécutent en série dans le conteneur Docker CK Quant local. Une preuve statistique manquante est affichée comme **non évaluée**, et le déploiement en paper trading exige une confirmation explicite de l'utilisateur. L'activation de capital réel reste une étape de confirmation manuelle distincte.

Voir [`desktop/README.md`](desktop/README.md) pour l'installation, l'activation et les détails de développement.

---

## Installation (Docker)

**Prérequis** : Docker avec Compose v2. Aucun environnement Python n'est nécessaire.

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

**Choix de l'image** :

| Image | Cas d'usage |
|---|---|
| `ericchenghz/ck-quant:stable` | Trading standard (recommandé) |
| `ericchenghz/ck-quant:stable-freqai` | Modèles FreqAI (LightGBM/XGBoost/RF) |
| `ericchenghz/ck-quant:stable-freqai-rl` | FreqAI + apprentissage par renforcement PyTorch |

Définissez `CK_QUANT_IMAGE` dans `.env` pour changer d'image.

### Configuration initiale

Après `new-config`, éditez `user_data/config.json` pour définir l'essentiel :

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

> **Commencez toujours par `dry_run: true`** (paper trading). Ne passez à
> `false` qu'une fois le comportement du bot et le P&L attendu compris.
> Pour les futures, créez des clés API avec **Enable Futures** coché.

### Placez votre stratégie et démarrez

```bash
# 1. Copy your private strategy into user_data/strategies/
# 2. Copy .env.example to .env and set CK_QUANT_STRATEGY to your class name
cp .env.example .env
#    CK_QUANT_STRATEGY=YourStrategyName

# 3. Start
docker compose up -d
docker compose logs -f --tail 200
```

La WebUI écoute par défaut sur <http://127.0.0.1:8080> (configurable via `CK_QUANT_WEBUI_BIND` / `CK_QUANT_WEBUI_PORT`).

La configuration, les stratégies, la base de données, les identifiants, les modèles et les logs vivent tous dans le
répertoire `user_data` local — **aucune donnée sensible n'entre dans l'image**.

> **Sécurité** : n'exposez jamais le port d'administration/API sur l'internet public.
> Utilisez un reverse proxy HTTPS ou un VPN de confiance, ainsi qu'un mot de passe
> fort et unique et un secret JWT. Testez d'abord sur une instance `dry_run`.

---

## Guides des fonctionnalités

### 1. WebUI multilingue et application Android

La WebUI embarque 7 langues et un espace d'administration authentifié :

- Éditez les paramètres de configuration courants ou complets, avec validation côté serveur avant enregistrement
- Éditez en ligne les paramètres ou les fichiers de stratégie
- Sauvegardes automatiques de la configuration et des stratégies, rechargement ou redémarrage sûr après enregistrement
- Consultez l'état d'exécution, gérez les ordres et les positions via l'API Freqtrade
- Consultez le journal d'audit de l'administration

L'administration est **désactivée par défaut** ; activez-la explicitement dans `config.json` :

```json
"ck_quant_admin": {
  "enabled": true,
  "config_edit": true,
  "strategy_edit": true
}
```

**APK Android** : à télécharger depuis
[GitHub Releases](https://github.com/ericchegncn/CK_Quant/releases/latest).
Après l'installation, saisissez l'adresse de votre serveur ainsi que l'identifiant et le mot de passe `api_server`.
Configuration complète, reverse proxy et notes de sécurité :
[docs/ck_quant_mobile_admin.md](docs/ck_quant_mobile_admin.md).

**Bot Telegram** : les mêmes 7 langues couvrent chaque message envoyé par le bot — notifications
d'ordres, `/status`, `/profit`, `/balance`, les rapports quotidiens/hebdomadaires/mensuels
et les erreurs que la couche RPC remonte dans la conversation. Choisissez la langue par
défaut dans `config.json` :

```json
"telegram": {
  "language": "zh-CN"
}
```

`/language` (alias `/lang`) change la langue d'une seule conversation à chaud
et le choix survit aux redémarrages (`user_data/bot_languages.json`). Référence et
liste complète des commandes : [docs/telegram-usage.md](docs/telegram-usage.md).

### 2. Pairlist Gainers/Losers (classement par variation en pourcentage)

Sélectionnez dynamiquement les plus fortes hausses et les plus fortes baisses, avec **deux modes** :

- `filter` (par défaut) : chaîne freqtrade native — classe uniquement dans la pairlist amont
- `union` : sélectionne sur l'ensemble du marché de façon indépendante et **fusionne** avec l'amont
  (Volume + Gainers + Static peuvent coexister)

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

Vérifiez avec :

```bash
docker compose run --rm CK_Quant test-pairlist \
    --userdir user_data --config user_data/config.json
```

Référence complète : [docs/gainers-losers-pairlist.md](docs/gainers-losers-pairlist.md).

### 3. Moteur de backtest au tick

Appariez les sorties sur de vraies séquences de ticks pour corriger la précision du backtest OHLCV :

```text
Within one 15m bar both stop-loss and take-profit are hit — which came first?
  OHLCV backtest: guesses (assumed path) → systematically optimistic ❌
  Tick backtest:  real tick sequence → exact ✅
```

Mesuré (ETH 2025-07, stop à 0,5 %) : 7,1 % des trades avaient leur ordre de déclenchement
mal jugé, et le sens du P&L net OHLCV était opposé au résultat tick réel.
Des stops plus serrés → une erreur plus grande.

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

Détails : [docs/advanced-tick-backtest.md](docs/advanced-tick-backtest.md).

### 4. Ordres iceberg synthétiques

Fractionnez un ordre important en tranches masquées ; l'exchange n'en voit jamais qu'une à la fois :

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

Détails : [docs/advanced-iceberg.md](docs/advanced-iceberg.md).

### 5. Publication en une commande

```bash
python scripts/release.py 2026.8          # build → push Docker Hub → tag → GitHub Release
python scripts/release.py 2026.8 --dry-run  # preview
```

### 6. Page de vitrine publique (accès invité)

Publiez en option un aperçu en lecture seule et uniquement agrégé, pour que les visiteurs sans compte puissent voir
comment un bot se comporte. Désactivé par défaut (l'endpoint public répond `404` tant qu'il est désactivé) :

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

Activez-le dans la configuration principale, sous forme de fichier overlay séparé ajouté avec un second `--config`, ou depuis
la WebUI (**Paramètres → Visibilité invité**), qui génère aussi un lien partageable
`/showcase?api=…&api=…` pour plusieurs bots. Les visiteurs ne voient jamais que les chiffres agrégés du premier écran du
tableau de bord — jamais les noms de paires, ni de stratégies, les lignes de trades, la configuration ou les clés — mais la page
publie tout de même vos performances et votre solde : décidez donc consciemment avant de la partager.

Détails : [docs/ck-quant-public-showcase.md](docs/ck-quant-public-showcase.md).

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

> Utilisez `--timeframe-detail 1m` pour des résultats fiables — les backtests en 15m pur sont
> systématiquement optimistes (surestimation mesurée de 12× sur un large échantillon).

---

## Freqtrade en amont

[![Freqtrade CI](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/freqtrade/freqtrade/actions/workflows/ci.yml)
[![DOI](https://joss.theoj.org/papers/10.21105/joss.04864/status.svg)](https://doi.org/10.21105/joss.04864)
[![codecov](https://codecov.io/gh/freqtrade/freqtrade/branch/develop/graph/badge.svg?token=AD5BG3ATKI)](https://codecov.io/gh/freqtrade/freqtrade)
[![Documentation](https://readthedocs.org/projects/freqtrade/badge/)](https://www.freqtrade.io)
[![Discord Server](https://img.shields.io/badge/Freqtrade_Discord-4E4E4E?logo=discord)](https://discord.gg/p7nuUNVfP7)

Freqtrade est un bot de trading de cryptomonnaies libre et open source, écrit en Python.
Il est conçu pour prendre en charge tous les principaux exchanges et être piloté via Telegram
ou une interface web. Il contient des outils de backtesting, de tracé et de gestion du capital,
ainsi que l'optimisation de stratégies par apprentissage automatique.

Ce projet est dérivé de Freqtrade et reste sous licence GPL-3.0. Voir
[CK_QUANT.md](CK_QUANT.md) pour les notes d'architecture.

## Clause de non-responsabilité

Ce logiciel est fourni à des fins éducatives uniquement. Ne risquez pas d'argent que
vous auriez peur de perdre. VOUS UTILISEZ CE LOGICIEL À VOS PROPRES RISQUES. LES AUTEURS
ET TOUS LES AFFILIÉS N'ASSUMENT AUCUNE RESPONSABILITÉ QUANT À VOS RÉSULTATS DE TRADING.

Commencez toujours par exécuter un bot de trading en Dry-Run et n'engagez pas d'argent
avant de comprendre comment il fonctionne et à quelles pertes ou quels profits vous devez
vous attendre.

Nous vous recommandons fortement de posséder des connaissances en programmation et en Python. N'hésitez pas
à lire le code source et à comprendre le mécanisme de ce bot.

---

## Licence

GPL-3.0 — voir [LICENSE](LICENSE).
