# CK Quant Docker quick start

CK Quant publishes a prebuilt CPU image to Docker Hub:

```text
ericchenghz/ck-quant:stable
```

The image contains CK Quant and its WebUI. It does **not** contain your
configuration, strategies, exchange keys, Telegram token, database, models, or
logs. Runtime data is mounted from the local `CK_Quant/user_data` directory.

## Linux quick start

Install Docker first. One optional third-party installer is:

```bash
bash <(curl -sSL https://cdn.jsdelivr.net/gh/SuperManito/LinuxMirrors@main/DockerInstallation.sh)
```

Review third-party scripts before executing them. You can instead use Docker's
official installation instructions for your Linux distribution.

Create the default directory and download the Compose file:

```bash
mkdir CK_Quant
cd CK_Quant
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/docker-compose.yml \
  -o docker-compose.yml
```

The raw GitHub download works for everyone only when the GitHub repository is
public. While the source repository is private, authenticated owners can
download the file from GitHub, or copy the Compose file manually. The public
Docker Hub image can still be pulled without GitHub access.

Pull the image and create the private runtime directory:

```bash
docker compose pull
docker compose run --rm ck-quant create-userdir --userdir user_data
```

Create a configuration interactively:

```bash
docker compose run --rm ck-quant new-config --config user_data/config.json
```

Copy your strategy to `user_data/strategies/`. If it is not named
`SampleStrategy`, create `.env` beside the Compose file:

```bash
curl -L https://raw.githubusercontent.com/ericchegncn/CK_Quant/main/.env.example \
  -o .env
nano .env
```

Set `CK_QUANT_STRATEGY` to the Python strategy class name. Keep
`CK_QUANT_CONFIG=config.json`, or change it to the filename inside
`user_data/`.

Start CK Quant:

```bash
docker compose up -d
docker compose ps
docker compose logs -f --tail 200
```

The WebUI is available at <http://127.0.0.1:8080> by default. Do not expose it
to the public internet without authentication, a firewall, and TLS.

## Updating

```bash
cd CK_Quant
docker compose pull
docker compose up -d
```

Compose replaces the container while retaining everything under `user_data`.
Back up the active SQLite database before an upgrade. Stop the bot before
copying a SQLite database and its WAL files.

## Common commands

```bash
docker compose stop
docker compose start
docker compose restart
docker compose logs -f --tail 200
docker compose down
```

`docker compose down` removes the container and network but does not delete the
bind-mounted `user_data` directory. Never add `--volumes` unless you understand
what will be removed.

## Image tags

- `stable`: recommended release for normal deployment.
- `latest`: currently the same tested release as `stable`.
- `sha-<commit>`: immutable build tied to one Git commit.
- `vX.Y.Z`: versioned release tag when a GitHub release is published.

## Maintainer publishing

The GitHub workflow `.github/workflows/ck-quant-docker-publish.yml` publishes
`stable`, `latest`, the Git version, and the commit tag when it is run manually
or when a `vX.Y.Z` Git tag is pushed. Configure these GitHub Actions secrets
before running it:

- `DOCKERHUB_USERNAME`;
- `DOCKERHUB_TOKEN` (use a Docker Hub personal access token, not an account
  password).

Manual publishing from Windows is also available:

```powershell
powershell -ExecutionPolicy Bypass `
  -File .\scripts\publish-ck-quant-image.ps1 `
  -Tag stable `
  -AlsoLatest
```

## Private runtime data

The repository ignores:

- `config*.json`;
- `user_data`;
- strategies placed in `user_data`;
- SQLite databases and WAL files;
- logs, models, credentials, keys, and exported image archives.

Before pushing changes, always run `git status` and confirm none of these files
are staged.
