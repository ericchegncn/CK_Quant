"""
Public, read-only *showcase* endpoint.

Exposes an aggregate-only view of a single bot so a public web page can display
the same headline numbers the authenticated dashboard shows on its first screen
(absolute USDT amounts included).  Each bot/server publishes its own instance -
no cross-bot aggregation happens here, that is the frontend's job.

The endpoint is:

* opt-in  — disabled by default, so it answers ``404`` exactly like an unknown
  route until ``api_server.public_showcase.enabled`` is switched on.  That way
  the URL never advertises its own existence.
* unauthenticated — it is mounted next to the other public router, so it must
  never grow into a second, unprotected copy of the regular API.
* sanitized — the payload carries numbers plus a display label only.  It
  deliberately contains **no** pair names, no strategy name, no per-trade /
  per-order rows, no ``best_pair`` / ``worst_pair`` style fields, no log lines,
  no config dump and no API credentials.  Absolute (stake currency) amounts are
  set to ``None`` - as one group, see ``ABSOLUTE_FIELDS`` - unless
  ``show_absolute`` is switched on.
* cached — a module level TTL cache keeps a public URL from turning into a CPU
  amplifier: the (comparatively expensive) aggregation runs at most once per
  ``cache_ttl_secs``, no matter how many anonymous requests arrive.

Nothing here recomputes trade maths; every number comes from the very same RPC
entry points the authenticated dashboard uses, so the public page cannot drift
away from it:

* the scalar block comes from ``RPC._rpc_trade_statistics`` - the ``"all"`` entry
  of ``/profit_all``, which is what the dashboard overview cards render.
* ``profit_history`` comes from ``RPC._rpc_profit_history`` - the exact series
  behind ``GET /profit_history`` (``ftbot.ts getProfitHistory()`` ->
  ``activeBot.profitHistory.data`` -> ``CumProfitChart``).
* ``starting_capital`` / ``balance_total`` mirror the dashboard balance card,
  i.e. ``RPC._rpc_balance()["total_bot"]`` (with a wallet based fallback).

Every ratio is a *ratio* (``1.0`` == ``+100%``); the frontend multiplies by 100.
Amounts are in ``stake_currency`` (USDT for the bots this ships with).

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

# Neutral fallback for the public display label.  A container name, a database
# name or a strategy name must never end up here - the repository is public and
# the strategies are private.
LABEL_DEFAULT = "Bot"
LABEL_MAX_LEN = 32
LABEL_ALLOWED_PUNCTUATION = " ._-"

CACHE_TTL_DEFAULT = 30

# Only these bot states are published; anything else collapses to "unknown".
_BOT_STATE_MAP = {"running": "running", "stopped": "stopped"}

# The scalar fields that carry an absolute amount in the stake currency (USDT).
# When ``show_absolute`` is off they are nulled as one group, so "hide the money"
# can never end up as a half-forgotten, per-field switch.  Keep in sync with
# ``PublicOverview`` - the unit tests assert the exact key set of the payload.
ABSOLUTE_FIELDS = (
    "expectancy",
    "trading_volume",
    "profit_total_abs",
    "profit_closed_abs",
    "profit_open_abs",
    "open_profit_abs",
    "starting_capital",
    "balance_total",
    "max_drawdown_abs",
    "current_drawdown_abs",
)


class PublicProfitPoint(BaseModel):
    """One point of the cumulative total-profit curve (same shape as /profit_history)."""

    date: int
    profit_abs: float


class PublicOverview(BaseModel):
    """Sanitized, aggregate-only overview of the bot - dashboard first screen."""

    bot_state: str
    runmode: str
    version: str
    exchange: str | None = None
    label: str = LABEL_DEFAULT
    trading_mode: str | None = None
    start_date: str | None = None
    uptime_seconds: int | None = None
    as_of: str
    # --- positions and trade counts ----------------------------------------
    open_trades: int
    max_open_trades: int
    trade_count: int
    # --- performance -------------------------------------------------------
    win_count: int
    loss_count: int
    win_rate: float | None = None
    profit_factor: float | None = None
    expectancy: float | None = None
    expectancy_ratio: float | None = None
    avg_duration_seconds: int | None = None
    # --- totals (absolute amounts are None unless show_absolute) -----------
    trading_volume: float | None = None
    profit_total_abs: float | None = None
    profit_total_ratio: float | None = None
    profit_closed_abs: float | None = None
    profit_closed_ratio: float | None = None
    profit_open_abs: float | None = None
    profit_open_ratio: float | None = None
    profit_total_ratio_sum: float | None = None
    profit_closed_ratio_sum: float | None = None
    starting_capital: float | None = None
    balance_total: float | None = None
    stake_currency: str | None = None
    # --- drawdown ----------------------------------------------------------
    max_drawdown_ratio: float | None = None
    max_drawdown_abs: float | None = None
    current_drawdown_ratio: float | None = None
    current_drawdown_abs: float | None = None
    # --- chart -------------------------------------------------------------
    open_profit_abs: float | None = None
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
    into the payload.  ``show_absolute`` defaults to *on* - the showcase page
    mirrors a dashboard that is denominated in stake currency amounts.
    """
    block = _showcase_block(config)
    return {
        "enabled": bool(block.get("enabled", False)),
        "label": normalize_label(block.get("label", LABEL_DEFAULT)),
        "show_absolute": bool(block.get("show_absolute", True)),
        "cache_ttl_secs": int(coerce_cache_ttl(block.get("cache_ttl_secs", CACHE_TTL_DEFAULT))),
    }


def _as_float(value: Any) -> float | None:
    """Return a finite float for ``value``, else None (guards bool/NaN/inf)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        # ``float("inf")`` is not valid JSON and would break the response.
        return None
    return number


def _difference(left: float | None, right: float | None) -> float | None:
    """``left - right`` when both sides are known, else None."""
    if left is None or right is None:
        return None
    return left - right


def _duration_seconds(value: Any) -> int | None:
    """Parse the RPC layer's ``avg_duration`` text (``H:MM:SS`` or ``D days, H:MM:SS``)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    days = 0
    if "," in text:
        head, _, tail = text.partition(",")
        head = head.strip()
        lowered = head.lower()
        if lowered.endswith(("day", "days")):
            head = head.split(" ", 1)[0]
        try:
            days = int(head)
        except ValueError:
            return None
        text = tail.strip()
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError:
        return None
    if min(hours, minutes, seconds, days) < 0:
        return None
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _iso_z(moment: datetime | None) -> str | None:
    """Render a datetime as an ISO-8601 UTC string with a trailing ``Z``."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_epoch_ms(value: Any) -> int | None:
    """Normalize a curve key (datetime/date/epoch s/epoch ms/ISO string) to epoch ms."""
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


def _balance_total(rpc: RPC, stake_currency: str, fiat_display_currency: str) -> float | None:
    """
    Total account value in the stake currency, matching the dashboard balance card.

    ``/balance``'s ``total_bot`` is what the authenticated UI renders, so the
    public page reports the same number.  The per-currency rows ``_rpc_balance``
    also returns (coin names!) are never touched, and a wallet based fallback
    keeps the public endpoint answering if the balance aggregation fails.
    """
    try:
        return _as_float(rpc._rpc_balance(stake_currency, fiat_display_currency).get("total_bot"))
    except Exception:
        logger.debug("public showcase: balance aggregation failed", exc_info=True)
    try:
        return _as_float(rpc._freqtrade.wallets.get_total_stake_amount())
    except Exception:  # pragma: no cover - defensive
        logger.debug("public showcase: wallet total unavailable", exc_info=True)
        return None


def _profit_history(
    rpc: RPC,
    show_absolute: bool,
    as_of: datetime,
    total_profit_abs: float | None,
    open_trades: int,
) -> list[dict[str, Any]]:
    """
    The dashboard's cumulative-profit curve, computed server side.

    Source of truth is ``RPC._rpc_profit_history`` - the same function behind
    ``GET /profit_history``, i.e. exactly the series the dashboard chart binds to
    (``ftbot.ts`` -> ``activeBot.profitHistory.data`` -> ``CumProfitChart``).  It
    walks the closed trades in close-date order and returns the running sum of
    their absolute profit, so no per-trade row ever leaves this module.

    The series is REALIZED only: it walks the closed trades in close-date order
    and returns the running sum of their absolute profit - the same red line the
    dashboard draws, which therefore ends at ``profit_closed_abs`` (a loss when
    the closed trades are down).  The still-open positions are NOT folded into
    this line: the dashboard draws them as a separate projection, and the public
    page does the same from the ``open_profit_abs`` field.  Mixing them into one
    line would make a losing bot look profitable, which is exactly what the user
    reported.

    With ``show_absolute`` off the series is withheld (empty list), because every
    point of it is an absolute amount.
    """
    if not show_absolute:
        return []

    try:
        curve = rpc._rpc_profit_history()
    except Exception:  # pragma: no cover - defensive, DB may be unavailable
        logger.debug("public showcase: profit history unavailable", exc_info=True)
        curve = None

    rows = curve.get("data", []) if isinstance(curve, dict) else []
    history: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = _to_epoch_ms(row.get("date"))
        value = _as_float(row.get("profit"))
        if timestamp is None or value is None:
            continue
        if history and timestamp <= history[-1]["date"]:
            timestamp = history[-1]["date"] + 1
        history.append({"date": timestamp, "profit_abs": round(value, 8)})

    projected = _as_float(total_profit_abs)
    _ = (projected, open_trades, as_of)  # kept for signature compatibility
    return history


def _build_public_overview(
    rpc: RPC, config: dict[str, Any], settings: dict[str, Any]
) -> dict[str, Any]:
    show_absolute = bool(settings["show_absolute"])
    now = datetime.now(UTC)
    stake_currency = config["stake_currency"]
    fiat_display_currency = config.get("fiat_display_currency", "")

    # Same entry point the dashboard overview cards read (/profit_all -> "all").
    stats = rpc._rpc_trade_statistics(stake_currency, fiat_display_currency)
    starting_balance = _as_float(rpc._freqtrade.wallets.get_starting_balance())
    start_dt = _bot_start_datetime(stats) or _earliest_trade_date()

    open_trades = Trade.get_open_trade_count()
    profit_total_abs = _as_float(stats.get("profit_all_coin"))
    profit_closed_abs = _as_float(stats.get("profit_closed_coin"))
    profit_total_ratio = _as_float(stats.get("profit_all_ratio"))
    profit_closed_ratio = _as_float(stats.get("profit_closed_ratio"))
    # Floating profit of the still-open positions - derived exactly like the
    # dashboard does it (total minus closed).
    profit_open_abs = _difference(profit_total_abs, profit_closed_abs)
    profit_open_ratio = _difference(profit_total_ratio, profit_closed_ratio)

    raw_max_open_trades = config.get("max_open_trades")
    try:
        max_open_trades = int(raw_max_open_trades) if raw_max_open_trades is not None else 0
    except (TypeError, ValueError):
        max_open_trades = 0

    payload: dict[str, Any] = {
        "bot_state": _BOT_STATE_MAP.get(str(rpc._freqtrade.state), "unknown"),
        "runmode": RunMode.DRY_RUN.value if config.get("dry_run") else RunMode.LIVE.value,
        "version": __version__,
        "exchange": (config.get("exchange") or {}).get("name"),
        "label": settings["label"],
        "trading_mode": config.get("trading_mode", "spot"),
        "start_date": _iso_z(start_dt),
        "uptime_seconds": int((now - start_dt).total_seconds()) if start_dt else None,
        "as_of": _iso_z(now),
        "open_trades": open_trades,
        "max_open_trades": max_open_trades,
        "trade_count": int(_as_float(stats.get("trade_count")) or 0),
        "win_count": int(_as_float(stats.get("winning_trades")) or 0),
        "loss_count": int(_as_float(stats.get("losing_trades")) or 0),
        "win_rate": _as_float(stats.get("winrate")),
        "profit_factor": _as_float(stats.get("profit_factor")),
        "expectancy": _as_float(stats.get("expectancy")),
        "expectancy_ratio": _as_float(stats.get("expectancy_ratio")),
        "avg_duration_seconds": _duration_seconds(stats.get("avg_duration")),
        "trading_volume": _as_float(stats.get("trading_volume")),
        "profit_total_abs": profit_total_abs,
        "profit_total_ratio": profit_total_ratio,
        "profit_closed_abs": profit_closed_abs,
        "profit_closed_ratio": profit_closed_ratio,
        "profit_open_abs": profit_open_abs,
        "profit_open_ratio": profit_open_ratio,
        "profit_total_ratio_sum": _as_float(stats.get("profit_all_ratio_sum")),
        "profit_closed_ratio_sum": _as_float(stats.get("profit_closed_ratio_sum")),
        "starting_capital": starting_balance,
        "balance_total": _balance_total(rpc, stake_currency, fiat_display_currency),
        "stake_currency": stake_currency,
        "max_drawdown_ratio": _as_float(stats.get("max_drawdown")),
        "max_drawdown_abs": _as_float(stats.get("max_drawdown_abs")),
        "current_drawdown_ratio": _as_float(stats.get("current_drawdown")),
        "current_drawdown_abs": _as_float(stats.get("current_drawdown_abs")),
        # Same value as ``profit_open_abs``; an own key because the chart binds
        # its open-profit projection to it.
        "open_profit_abs": profit_open_abs,
        "profit_history": _profit_history(rpc, show_absolute, now, profit_total_abs, open_trades),
    }

    if not show_absolute:
        # Amounts (and, above, the curve) are withheld as one group.
        for field in ABSOLUTE_FIELDS:
            payload[field] = None
    return payload


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
