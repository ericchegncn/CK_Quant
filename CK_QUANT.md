# CK Quant

CK Quant is a Freqtrade-based quantitative trading distribution focused on
operational safety, large-order execution, and a card-oriented web interface.

## Project boundaries

- The Python package remains `freqtrade` so existing strategies and tooling stay
  compatible.
- Live configuration, strategies, databases, logs, models, exchange credentials,
  Telegram credentials, and server-specific files are runtime data. They are
  excluded from Git and from the Docker build context.
- A container receives runtime data only through a local `user_data` bind mount.
- Changes derived from Freqtrade remain licensed under GPL-3.0. Upstream
  attribution and the original license are retained.

## Initial roadmap

1. Safe exchange-order recovery for rapid stop-and-reverse workflows.
2. Synthetic iceberg execution for entries and exits, disabled by default.
3. CK Quant UI with an iOS-inspired translucent card system.
4. Reproducible CPU and FreqAI Docker images.

Never commit a real `config*.json` or any file from a live `user_data` folder.

## Synthetic iceberg configuration

The feature is disabled by default. Merge the following section into a local
runtime configuration:

```json
{
  "iceberg_orders": {
    "enabled": true,
    "entry": true,
    "exit": true,
    "visible_ratio": 0.1,
    "max_slices": 10,
    "min_slice_stake": 25,
    "replenish_interval": 5,
    "size_jitter": 0.15
  }
}
```

`visible_ratio` is the normal visible child size. `max_slices` also establishes
a minimum child size, so the plan cannot grow without bound. `min_slice_stake`
must be chosen above the exchange minimum. Regular signal/custom exits may be
sliced; stop-loss, liquidation, emergency, and forced exits always bypass the
iceberg so risk controls are never delayed.

## Build the Docker images

From the repository root:

```bash
docker build -t ck-quant:local .
docker build -f docker/Dockerfile.ck-quant-freqai \
  --build-arg sourceimage=ck-quant --build-arg sourcetag=local \
  -t ck-quant:freqai .
docker build -f docker/Dockerfile.ck-quant-freqai-rl \
  --build-arg sourceimage=ck-quant --build-arg sourcetag=freqai \
  -t ck-quant:freqai-rl .
```

The public CPU image is `ericchenghz/ck-quant:stable`. The root
`docker-compose.yml` can be downloaded and used directly:

```bash
mkdir CK_Quant
cd CK_Quant
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml
docker compose pull
docker compose run --rm ck-quant create-userdir --userdir user_data
```

The image itself contains no strategies, configuration, databases, models,
credentials, or server data. See `docs/ck-quant-docker.md` for the complete
deployment and update workflow.
