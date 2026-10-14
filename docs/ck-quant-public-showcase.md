# Public showcase page (guest access)

CK Quant can publish a **public, read-only, aggregate-only** overview of a running bot so that
people without an account can see how it performs. It backs the `/showcase` page, which is the
only page an anonymous visitor can reach besides the login screen.

!!! note
    The feature is **disabled by default**. While it is off, the public endpoint answers `404`
    exactly like an unknown route, so the URL never advertises its own existence.

## What a visitor sees

The showcase page is the dashboard's first screen and nothing else:

- aggregate figures only — bot state, cumulative profit curve (realized, with the open-position
  projection drawn as a separate series), two ROI cards (all trades / closed trades) and the
  metric grid (trade count, win rate, expectancy, profit factor, drawdown, trading volume, …);
- **no** pair names, **no** strategy name, **no** per-trade or per-order rows, **no** log lines,
  **no** config dump and **no** credentials;
- the numbers come from the same RPC entry points the authenticated dashboard uses
  (`/profit_all`, `/profit_history`, `/balance`), so the public page cannot drift away from it;
- every page section other than the showcase is unreachable while logged out — the router sends
  guests to `/showcase`, and only `/showcase` and `/login` are reachable. No top/bottom navigation
  and no authentication requests are issued for a guest.

## Configuration keys

All four keys live under `api_server.public_showcase`:

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

| Key | Type / default | Meaning |
|---|---|---|
| `enabled` | bool, `false` | Master switch. While `false` the public endpoint returns `404`. |
| `label` | string, `"Bot"`, max 32 chars | Display name used as the block heading on the showcase page. A value that looks like a strategy, container or database name is replaced by the neutral default `Bot`: only letters, digits, spaces and `._-` are allowed, at most 32 characters, and an underscore followed by a digit is rejected (so a name like `my_bot_15m` never becomes public). |
| `show_absolute` | bool, `true` | Whether absolute stake-currency (USDT) amounts are published. When set to `false`, all absolute fields are nulled **as one group** (profit/expectancy/trading volume/max drawdown/starting capital/balance/fiat amounts) while the ratios stay — so "hide the money" can never end up as a half-forgotten per-field switch. |
| `cache_ttl_secs` | integer, `30`, min `0` | TTL of the server-side cache for the public payload. The aggregation runs at most once per TTL, so a shared URL cannot be turned into a CPU amplifier no matter how many anonymous requests arrive. `0` disables caching. |

`cache_ttl_secs` can only be changed in the configuration file; the WebUI toggle exposes
`enabled`, `label` and `show_absolute` only (saving from the WebUI keeps the configured TTL).

## Three ways to enable it

### 1. Inside the main configuration file

Merge the block above into the `api_server` section of the config you already use, then restart
the bot. This is the simplest option when the bot has a single configuration file.

### 2. As an overlay via a second `--config`

Keep the public settings in a separate file that is mounted into the container with the rest of
`user_data` (it is not part of the image and not in Git), and append it as a second `--config`:

```yaml
    command: >
      trade
      --userdir /CK_Quant/user_data
      --config /CK_Quant/user_data/config.json
      --config /CK_Quant/user_data/config_public_showcase.json
      --strategy YourStrategy
```

Freqtrade merges later `--config` files over earlier ones. Deleting the last `--config` line
turns the showcase off again without touching the main configuration.

### 3. From the WebUI (Settings → Guest visibility)

Once logged in, open **Settings** and find the **Guest visibility** (`游客可见`) block. For every
configured bot you get:

- **Allow visitors to view the first screen** (`允许游客查看首屏`) — the `enabled` switch;
- a **display name** field — the `label`, empty means "use the bot name";
- **Show absolute profit** (`显示绝对收益`) — the `show_absolute` switch;
- **Save settings** — validates, backs up and atomically writes the configuration file, then
  reloads it where possible;
- **Generate share link** and **Copy**.

Bots running an image that predates the admin endpoint report "this bot does not support the
online switch yet — enable the public showcase in the server configuration file" instead.

## Sharing the link

The generated link always points at `/showcase` and carries the API base URL(s) as `api`
parameters (repeatable):

```text
https://your-host/showcase?api=https://bot-a.example.com&api=https://bot-b.example.com
```

Each `api` value is a bot base URL, so one page can show several bots side by side; the same
origin is used when the parameter is missing. The link contains **only base URLs — no tokens and
no keys**, so it is safe to hand out. A bot that has the showcase disabled shows a neutral
"this bot does not publish a showcase" card.

To stop publishing:

- delete the overlay file / the second `--config` line (option 2), or
- set `"enabled": false` in the configuration file (options 1 and 2), or
- switch **Allow visitors to view the first screen** off in the WebUI (option 3).

## Security considerations

- The endpoint is mounted without authentication and is deliberately kept minimal: it must never
  grow into a second, unprotected copy of the regular API.
- It still publishes **your performance and your balance** to anyone holding the link. Absolute
  amounts are included unless you turn `show_absolute` off. Decide deliberately whether that is
  acceptable for the bot you expose, and never share a link to a bot whose strategy identity
  would be obvious from its numbers alone.
- Keep the WebUI itself behind HTTPS and a strong password; the showcase page is public, the admin
  settings behind it are not.
