"""
Public, read-only *showcase* endpoint.

Exposes a small, aggregate-only view of a single bot so a public web page can
display it.  Each bot/server publishes its own instance - no cross-bot
aggregation happens here, that is the frontend's job.

The endpoint is:

* opt-in  — disabled by default, so it answers ``404`` exactly like an unknown
  route until ``api_server.public_showcase.enabled`` is switched on.  That way
  the URL never advertises its own existence.
* unauthenticated — it is mounted next to the other public router, so it must
  never grow into a second, unprotected copy of the regular API.
* sanitized — the payload carries numbers plus a display label only.  It
  deliberately contains **no** pair names, no strategy name, no per-trade /
  per-order rows, no ``best_pair`` / ``worst_pair`` style fields, no log lines,
  no config dump, no API credentials and - unless ``show_absolute`` is on - no
  balances at all.
* cached — a module level TTL cache keeps a public URL from turning into a CPU
  amplifier: the (comparatively expensive) aggregation runs at most once per
  ``cache_ttl_secs``, no matter how many anonymous requests arrive.

All numbers reuse the RPC layer's existing aggregates (``_rpc_trade_statistics``
and the daily time-unit profit curve); nothing here recomputes trade maths.
Every ratio is a *ratio* (``1.0`` == ``+100%``); the frontend multiplies by 100.

This module also owns the label rules, which the authenticated admin endpoints
(``api_ck_quant_admin``) reuse when an operator edits the showcase settings.
"""

import logging
import math
import threading
import time as _time
from datetime import UTC, date, datetime
from datetime import time as _dt_time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from freqtrade import __version__
from freqtrade.enums import RunMode
from freqtrade.persistence import Trade
from freqtrade.rpc.api_server.deps import get_config, get_rpc
from freqtrade.rpc.rpc import RPC


logger = logging.getLogger(__name__)

router = APIRouter()

# Hard ceiling on the number of daily buckets pulled from the existing
# aggregation.  The effective window is additionally clipped to the bot's own
# runtime, so a young bot does not issue hundreds of empty per-day queries.
MAX_HISTORY_DAYS = 365

# Neutral fallback for the public display label.  A container name, a database
# name or a strategy name must never end up here - the repository is public and
# the strategies are private.
LABEL_DEFAULT = "Bot"
LABEL_MAX_LEN = 32
LABEL_ALLOWED_PUNCTUATION = " ._-"

CACHE_TTL_DEFAULT = 30

# Only these bot states are published; anything else collapses to "unknown".
_BOT_STATE_MAP = {"running": "running", "stopped": "stopped"}


class PublicProfitPoint(BaseModel):
    """A single point of the cumulative profit curve."""

    date: int
    profit: float


class PublicOverview(BaseModel):
    """Sanitized, aggregate-only overview of the bot."""

    bot_state: str
    runmode: str
    version: str
    exchange: str | None = None
    label: str = LABEL_DEFAULT
    trading_mode: str | None = None
    start_date: str | None = None
    uptime_seconds: int | None = None
    open_trades: int
    trade_count: int
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    max_drawdown_ratio: float | None = None
    profit_total_ratio: float | None = None
    profit_closed_ratio: float | None = None
    profit_abs: float | None = None
    starting_capital: float | None = None
    as_of: str
    profit_history: list[PublicProfitPoint] = Field(default_factory=list)


# --- module level TTL cache -------------------------------------------------
# The payload is already JSON-ready, so caching it is cheap.  A signature guards
# against two different configurations (e.g. show_absolute toggled) sharing one
# entry.
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"payload": None, "ts": 0.0, "signature": None}


def _cache_read(signature: tuple, ttl: float) -> dict[str, Any] | None:
    if ttl <= 0:
        return None
    with _CACHE_LOCK:
        payload = _CACHE["payload"]
        if (
            payload is not None
            and _CACHE["signature"] == signature
            and (_time.monotonic() - _CACHE["ts"]) < ttl
        ):
            return payload
    return None


def _cache_write(signature: tuple, payload: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _CACHE["payload"] = payload
        _CACHE["signature"] = signature
        _CACHE["ts"] = _time.monotonic()


# --- label rules (shared with the authenticated admin endpoints) -------------


def label_problem(label: Any) -> str | None:
    """
    Return a human readable reason why ``label`` may not be published, else None.

    A label ends up on a public page, so it is restricted to a harmless character
    set.  The ``_<digit>`` rule exists because private strategy sources are named
    ``<name>_<number><unit>``; refusing that shape guarantees a strategy name can
    never travel through this field.
    """
    if not isinstance(label, str):
        return "label must be a string"
    value = label.strip()
    if not value:
        return "label must not be empty"
    if len(value) > LABEL_MAX_LEN:
        return f"label must be at most {LABEL_MAX_LEN} characters"
    for char in value:
        if not (char.isalnum() or char in LABEL_ALLOWED_PUNCTUATION):
            return "label may only contain letters, digits, spaces and ' ._-'"
    lowered = value.lower()
    for index, char in enumerate(lowered):
        if char.isdigit() and index and lowered[index - 1] == "_":
            return "label must not contain an underscore followed by a digit"
    return None


def normalize_label(value: Any) -> str:
    """Return a publishable label, falling back to the neutral default."""
    if label_problem(value) is not None:
        return LABEL_DEFAULT
    return str(value).strip()


def coerce_cache_ttl(value: Any) -> float:
    """Return the configured TTL in seconds; ``0`` means caching is disabled."""
    try:
        ttl = float(value)
    except (TypeError, ValueError):
        return float(CACHE_TTL_DEFAULT)
    if math.isnan(ttl):
        return float(CACHE_TTL_DEFAULT)
    return ttl if ttl > 0 else 0.0


def _showcase_block(config: dict[str, Any]) -> dict[str, Any]:
    """Return the raw ``api_server.public_showcase`` block (empty dict if unset)."""
    api_server = config.get("api_server") or {}
    if not isinstance(api_server, dict):
        return {}
    block = api_server.get("public_showcase") or {}
    return block if isinstance(block, dict) else {}


def showcase_settings(config: dict[str, Any]) -> dict[str, Any]:
    """
    Normalized view of the four showcase settings.

    Single source of truth for both the public endpoint and the authenticated
    admin endpoints, so a hand-edited config file cannot smuggle an unsafe label
    into the payload.
    """
    block = _showcase_block(config)
    return {
        "enabled": bool(block.get("enabled", False)),
        "label": normalize_label(block.get("label", LABEL_DEFAULT)),
        "show_absolute": bool(block.get("show_absolute", False)),
        "cache_ttl_secs": int(coerce_cache_ttl(block.get("cache_ttl_secs", CACHE_TTL_DEFAULT))),
    }


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_z(moment: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 UTC string with a trailing ``Z``."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_epoch_ms(value: Any) -> int | None:
    """Normalize the daily-curve key to epoch milliseconds."""
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
    elif isinstance(value, date):
        moment = datetime.combine(value, _dt_time.min, tzinfo=UTC)
    elif isinstance(value, bool):
        return None
    elif isinstance(value, (int, float)):
        # Already an epoch value - assume milliseconds when it is big enough to be one.
        return int(value) if value > 1e11 else int(value * 1000)
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
    else:
        return None
    return int(moment.timestamp() * 1000)


def _bot_start_datetime(stats: dict[str, Any]) -> datetime | None:
    timestamp = stats.get("bot_start_timestamp") or 0
    if timestamp:
        return datetime.fromtimestamp(timestamp / 1000, tz=UTC)
    return None


def _earliest_trade_date() -> datetime | None:
    """Fallback start date: the open date of the oldest trade, if any."""
    try:
        value = Trade.session.execute(select(func.min(Trade.open_date))).scalar()
    except Exception:  # pragma: no cover - defensive, DB may be unavailable
        logger.debug("public showcase: could not read earliest trade date", exc_info=True)
        return None
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _profit_history(
    rpc: RPC,
    config: dict[str, Any],
    show_absolute: bool,
    starting_balance: float | None,
    start_dt: datetime | None,
) -> list[dict[str, Any]]:
    """
    Map the RPC layer's daily profit curve onto ascending ``{date, profit}`` points.

    ``profit`` is the *cumulative* value: an absolute amount when ``show_absolute``
    is on, a ratio of the starting capital otherwise.  Days without any realized
    profit are dropped - the cumulative value does not change on them, so the
    chart is identical while the payload stays small.
    """
    window_days = MAX_HISTORY_DAYS
    if start_dt is not None:
        elapsed = (datetime.now(UTC) - start_dt).days + 1
        window_days = max(1, min(MAX_HISTORY_DAYS, elapsed))

    curve = rpc._rpc_timeunit_profit(
        window_days,
        config["stake_currency"],
        config.get("fiat_display_currency", ""),
        "days",
    )

    buckets: list[tuple[int, float]] = []
    for row in curve.get("data", []):
        timestamp = _to_epoch_ms(row.get("date"))
        if timestamp is None:
            continue
        buckets.append((timestamp, _as_float(row.get("abs_profit")) or 0.0))
    buckets.sort(key=lambda item: item[0])

    history: list[dict[str, Any]] = []
    cumulative = 0.0
    for timestamp, amount in buckets:
        cumulative += amount
        if amount == 0.0:
            continue
        if show_absolute:
            value = cumulative
        elif starting_balance:
            value = cumulative / float(starting_balance)
        else:
            value = 0.0
        history.append({"date": timestamp, "profit": round(value, 8)})
    return history


def _build_public_overview(
    rpc: RPC, config: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    show_absolute = bool(settings["show_absolute"])
    now = datetime.now(UTC)
    stats = rpc._rpc_trade_statistics(config["stake_currency"], config.get("fiat_display_currency"))
    starting_balance = _as_float(rpc._freqtrade.wallets.get_starting_balance())

    start_dt = _bot_start_datetime(stats) or _earliest_trade_date()

    return {
        "bot_state": _BOT_STATE_MAP.get(str(rpc._freqtrade.state), "unknown"),
        "runmode": RunMode.DRY_RUN.value if config.get("dry_run") else RunMode.LIVE.value,
        "version": __version__,
        "exchange": (config.get("exchange") or {}).get("name"),
        "label": settings["label"],
        "trading_mode": config.get("trading_mode", "spot"),
        "start_date": _iso_z(start_dt),
        "uptime_seconds": int((now - start_dt).total_seconds()) if start_dt else None,
        "open_trades": Trade.get_open_trade_count(),
        "trade_count": int(_as_float(stats.get("trade_count")) or 0),
        "win_rate": _as_float(stats.get("winrate")),
        "profit_factor": _as_float(stats.get("profit_factor")),
        "expectancy": _as_float(stats.get("expectancy")),
        "max_drawdown_ratio": _as_float(stats.get("max_drawdown")),
        "profit_total_ratio": _as_float(stats.get("profit_all_ratio")),
        "profit_closed_ratio": _as_float(stats.get("profit_closed_ratio")),
        # Balances are withheld unless explicitly enabled - this is the field most
        # likely to be considered sensitive.
        "profit_abs": _as_float(stats.get("profit_all_coin")) if show_absolute else None,
        "starting_capital": starting_balance if show_absolute else None,
        "as_of": _iso_z(now),
        "profit_history": _profit_history(rpc, config, show_absolute, starting_balance, start_dt),
    }


@router.get("/public/overview", response_model=PublicOverview, tags=["Info"])
def public_overview(rpc: RPC = Depends(get_rpc), config=Depends(get_config)):
    """Public, read-only, sanitized overview of the bot (no authentication)."""
    settings = showcase_settings(config)
    if not settings["enabled"]:
        # Answer exactly like an unknown route so the endpoint's existence
        # is not disclosed while it is switched off.
        raise HTTPException(status_code=404, detail="Not Found")

    signature = (settings["show_absolute"], settings["label"])
    cached = _cache_read(signature, coerce_cache_ttl(settings["cache_ttl_secs"]))
    if cached is not None:
        return cached

    payload = _build_public_overview(rpc, config, settings)
    _cache_write(signature, payload)
    return payload
