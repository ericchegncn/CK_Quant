"""
Unit tests for the public, read-only showcase endpoint and its authenticated toggle.

Contract under test:

* ``GET /api/v1/public/overview`` requires **no** authentication, answers ``404``
  while the feature is disabled and exposes exactly the documented aggregate
  fields - never a pair, a strategy name, a per-trade row or a balance.
* ``GET|POST /api/v1/ck_quant/public_showcase`` is the authenticated way to read
  and change the same settings (and persists them to the active config file).
"""

import json
from unittest.mock import MagicMock, PropertyMock

import pytest
from fastapi.testclient import TestClient
from requests.auth import _basic_auth_str

from freqtrade import __version__
from freqtrade.enums import RunMode
from freqtrade.loggers import setup_logging, setup_logging_pre
from freqtrade.rpc import RPC
from freqtrade.rpc.api_server import ApiServer, api_public_showcase
from freqtrade.rpc.api_server.api_public_showcase import (
    LABEL_DEFAULT,
    label_problem,
    normalize_label,
)
from tests.conftest import EXMS, create_mock_trades_usdt, get_patched_freqtradebot


BASE_URI = "/api/v1"
OVERVIEW_URI = f"{BASE_URI}/public/overview"
SHOWCASE_URI = f"{BASE_URI}/ck_quant/public_showcase"

_TEST_USER = "FreqTrader"
_TEST_PASS = "SuperSecurePassword1!"
_TEST_WS_TOKEN = "secret_Ws_t0ken"
_JWT_SECRET_KEY = "99980ff8fcf77f21ef610adb46b788c505b8483897bc26203b5591eefe0d15"

SHOWCASE_DEFAULTS = {
    "enabled": False,
    "label": LABEL_DEFAULT,
    "show_absolute": False,
    "cache_ttl_secs": 30,
}

# The complete, frozen key set of the public payload.  Adding a field without
# updating this set is a contract change, not a cosmetic one.
PUBLIC_OVERVIEW_KEYS = {
    "as_of",
    "bot_state",
    "exchange",
    "expectancy",
    "label",
    "max_drawdown_ratio",
    "open_trades",
    "profit_abs",
    "profit_closed_ratio",
    "profit_factor",
    "profit_history",
    "profit_total_ratio",
    "runmode",
    "starting_capital",
    "start_date",
    "trade_count",
    "trading_mode",
    "uptime_seconds",
    "version",
    "win_rate",
}

# Markers that must never appear anywhere in the public payload.
FORBIDDEN_MARKERS = (
    "/USDT",
    "best_pair",
    "worst_pair",
    "strategy",
    "api_key",
    "apiKey",
    "secret",
    "password",
    "NEO",
)


def _admin_headers() -> dict[str, str]:
    return {
        "Authorization": _basic_auth_str(_TEST_USER, _TEST_PASS),
        "Origin": "http://example.com",
    }


def _write_config_file(tmp_path, showcase: dict) -> "object":
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps({"api_server": {"public_showcase": showcase}}, indent=4),
        encoding="utf-8",
    )
    return config_file


@pytest.fixture
def showcase_client(default_conf, mocker, tmp_path):
    setup_logging_pre()
    setup_logging(default_conf)
    default_conf["runmode"] = RunMode.DRY_RUN
    default_conf["user_data_dir"] = tmp_path
    default_conf["tradable_balance_ratio"] = 1
    default_conf["api_server"] = {
        "enabled": True,
        "listen_ip_address": "127.0.0.1",
        "listen_port": 8080,
        "CORS_origins": ["http://example.com"],
        "jwt_secret_key": _JWT_SECRET_KEY,
        "username": _TEST_USER,
        "password": _TEST_PASS,
        "ws_token": _TEST_WS_TOKEN,
        "public_showcase": dict(SHOWCASE_DEFAULTS),
    }
    default_conf["ck_quant_admin"] = {
        "enabled": True,
        "config_edit": True,
        "strategy_edit": False,
    }
    config_file = _write_config_file(tmp_path, dict(SHOWCASE_DEFAULTS))
    default_conf["config_files"] = [str(config_file)]

    ftbot = get_patched_freqtradebot(mocker, default_conf)
    rpc = RPC(ftbot)
    mocker.patch("freqtrade.rpc.api_server.ApiServer.start_api", MagicMock())
    apiserver = None
    try:
        apiserver = ApiServer(default_conf)
        apiserver.add_rpc_handler(rpc)
        with TestClient(apiserver.app) as client:
            yield ftbot, client, config_file
    finally:
        if apiserver:
            apiserver.cleanup()
        ApiServer.shutdown()


def _patch_exchange(mocker, ticker, fee, markets) -> None:
    mocker.patch.multiple(
        EXMS,
        get_balances=MagicMock(return_value=ticker),
        fetch_ticker=ticker,
        get_fee=fee,
        markets=PropertyMock(return_value=markets),
    )


def _configure(ftbot, *, enabled: bool, label=LABEL_DEFAULT, show_absolute=False, ttl=0) -> None:
    """Point the running bot at a showcase configuration (ttl=0 disables caching)."""
    ftbot.config["api_server"]["public_showcase"] = {
        "enabled": enabled,
        "label": label,
        "show_absolute": show_absolute,
        "cache_ttl_secs": ttl,
    }


# --- label rules -------------------------------------------------------------


@pytest.mark.parametrize("label", ["Demo Bot", "  Demo Bot  ", "Bot", "demo.bot-1"])
def test_label_problem_accepts_harmless_labels(label):
    assert label_problem(label) is None
    assert normalize_label(label) == label.strip()


@pytest.mark.parametrize(
    "label",
    [
        None,
        123,
        "",
        "   ",
        "bot/name",
        "bot\\name",
        "bot_1",
        "x" * 33,
        "na\x00me",
    ],
)
def test_label_problem_rejects_unsafe_labels(label):
    assert label_problem(label) is not None
    assert normalize_label(label) == LABEL_DEFAULT


# --- public endpoint ---------------------------------------------------------


def test_public_overview_disabled_is_404(showcase_client):
    """Disabled by default: the URL must look like it does not exist."""
    _, client, _ = showcase_client

    rc = client.get(OVERVIEW_URI)

    assert rc.status_code == 404
    assert rc.json() == {"detail": "Not Found"}


def test_public_overview_enabled_without_token_exact_contract(
    showcase_client, mocker, ticker, fee, markets
):
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    _configure(ftbot, enabled=True, label="Demo Bot")
    create_mock_trades_usdt(fee, is_short=None)

    # Deliberately no Authorization header at all.
    rc = client.get(OVERVIEW_URI)

    assert rc.status_code == 200
    payload = rc.json()
    assert set(payload) == PUBLIC_OVERVIEW_KEYS

    assert payload["label"] == "Demo Bot"
    assert payload["version"] == __version__
    assert payload["exchange"] == "binance"
    assert payload["bot_state"] == "running"
    assert payload["runmode"] == "dry_run"
    assert payload["trading_mode"] == "spot"
    assert payload["start_date"] is not None
    assert payload["start_date"].endswith("Z")
    assert payload["as_of"].endswith("Z")
    assert isinstance(payload["uptime_seconds"], int)
    assert payload["open_trades"] >= 0
    assert payload["trade_count"] == 7
    assert isinstance(payload["as_of"], str)


def test_public_overview_payload_is_sanitized(showcase_client, mocker, ticker, fee, markets):
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    _configure(ftbot, enabled=True, show_absolute=True)
    create_mock_trades_usdt(fee, is_short=None)

    rc = client.get(OVERVIEW_URI)

    assert rc.status_code == 200
    payload = rc.json()
    body = json.dumps(payload)
    for marker in FORBIDDEN_MARKERS:
        assert marker not in body, f"payload leaked {marker!r}"
        assert marker not in rc.text, f"raw body leaked {marker!r}"

    # No nested containers except the documented profit curve - i.e. no trade
    # list, no order list and no pair keyed mapping can hide in there.
    for key, value in payload.items():
        if key == "profit_history":
            continue
        assert not isinstance(value, (dict, list)), f"{key} must stay a scalar"


def test_public_overview_absolute_toggle(showcase_client, mocker, ticker, fee, markets):
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    create_mock_trades_usdt(fee, is_short=None)

    _configure(ftbot, enabled=True, label="Relative", show_absolute=False)
    relative = client.get(OVERVIEW_URI).json()
    assert relative["profit_abs"] is None
    assert relative["starting_capital"] is None
    assert isinstance(relative["profit_total_ratio"], float)

    _configure(ftbot, enabled=True, label="Absolute", show_absolute=True)
    absolute = client.get(OVERVIEW_URI).json()
    assert isinstance(absolute["profit_abs"], (int, float))
    assert not isinstance(absolute["profit_abs"], bool)
    assert isinstance(absolute["starting_capital"], (int, float))
    assert not isinstance(absolute["starting_capital"], bool)


def test_public_overview_profit_history_shape(showcase_client, mocker, ticker, fee, markets):
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    _configure(ftbot, enabled=True, label="Curve")
    create_mock_trades_usdt(fee, is_short=None)

    history = client.get(OVERVIEW_URI).json()["profit_history"]

    assert history
    dates = [point["date"] for point in history]
    assert dates == sorted(dates)
    for point in history:
        assert set(point) == {"date", "profit"}
        assert isinstance(point["date"], int)
        assert isinstance(point["profit"], float)


@pytest.mark.parametrize("unsafe_label", ["bot/name", "bot_1", "x" * 33, "   "])
def test_public_overview_sanitizes_hand_edited_label(
    showcase_client, mocker, ticker, fee, markets, unsafe_label
):
    """A label written straight into the config file must not reach the payload."""
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    _configure(ftbot, enabled=True, label=unsafe_label)

    payload = client.get(OVERVIEW_URI).json()

    assert payload["label"] == LABEL_DEFAULT


def test_public_overview_caches_within_ttl(showcase_client, mocker, ticker, fee, markets):
    ftbot, client, _ = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    _configure(ftbot, enabled=True, label="CacheCheck", ttl=60)
    spy = mocker.patch(
        "freqtrade.rpc.api_server.api_public_showcase._build_public_overview",
        wraps=api_public_showcase._build_public_overview,
    )

    first = client.get(OVERVIEW_URI)
    second = client.get(OVERVIEW_URI)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    # The expensive aggregation ran once, not once per anonymous request.
    assert spy.call_count == 1


# --- authenticated toggle ----------------------------------------------------


def test_showcase_admin_requires_authentication(showcase_client):
    _, client, _ = showcase_client

    assert client.get(SHOWCASE_URI).status_code == 401
    assert client.post(SHOWCASE_URI, json={"enabled": True}).status_code == 401


def test_showcase_admin_get_reports_current_settings(showcase_client):
    _, client, _ = showcase_client

    rc = client.get(SHOWCASE_URI, headers=_admin_headers())

    assert rc.status_code == 200
    assert rc.json() == {**SHOWCASE_DEFAULTS, "config_writable": True}


def test_showcase_admin_post_persists_and_takes_effect(
    showcase_client, mocker, ticker, fee, markets
):
    ftbot, client, config_file = showcase_client
    _patch_exchange(mocker, ticker, fee, markets)
    reload_spy = mocker.patch(
        "freqtrade.rpc.rpc.RPC._rpc_reload_config",
        MagicMock(return_value={"status": "Reloading config ..."}),
    )

    rc = client.post(
        SHOWCASE_URI,
        json={"enabled": True, "label": "Live Account", "show_absolute": True},
        headers=_admin_headers(),
    )

    assert rc.status_code == 200
    body = rc.json()
    assert body["enabled"] is True
    assert body["label"] == "Live Account"
    assert body["show_absolute"] is True
    assert body["cache_ttl_secs"] == 30

    # Persisted to the active configuration file ...
    document = json.loads(config_file.read_text(encoding="utf-8"))
    assert document["api_server"]["public_showcase"] == {
        "enabled": True,
        "label": "Live Account",
        "show_absolute": True,
        "cache_ttl_secs": 30,
    }
    # ... using the admin module's usual safety net (backup + audit trail)
    user_data_dir = ftbot.config["user_data_dir"]
    assert list((user_data_dir / "backups" / "ck_quant_admin").iterdir())
    assert (user_data_dir / "logs" / "ck_quant_admin_audit.jsonl").is_file()
    # ... and asking the bot to reload so it becomes effective immediately
    assert reload_spy.call_count == 1

    # The public page now serves the new label, still without any token.
    public = client.get(OVERVIEW_URI)
    assert public.status_code == 200
    assert public.json()["label"] == "Live Account"
    assert isinstance(public.json()["profit_abs"], (int, float))


def test_showcase_admin_post_merges_partial_payload(showcase_client, mocker):
    _ftbot, client, config_file = showcase_client
    mocker.patch(
        "freqtrade.rpc.rpc.RPC._rpc_reload_config",
        MagicMock(return_value={"status": "Reloading config ..."}),
    )
    client.post(
        SHOWCASE_URI,
        json={"enabled": True, "label": "First"},
        headers=_admin_headers(),
    )

    rc = client.post(SHOWCASE_URI, json={"enabled": False}, headers=_admin_headers())

    assert rc.status_code == 200
    body = rc.json()
    # Only `enabled` changed; the previously stored label/flag survive.
    assert body["enabled"] is False
    assert body["label"] == "First"
    assert body["show_absolute"] is False
    document = json.loads(config_file.read_text(encoding="utf-8"))
    assert document["api_server"]["public_showcase"]["label"] == "First"
    assert document["api_server"]["public_showcase"]["enabled"] is False


@pytest.mark.parametrize("unsafe_label", ["bot/name", "bot_1", "x" * 33, "", "   "])
def test_showcase_admin_post_rejects_unsafe_label(showcase_client, unsafe_label):
    _, client, config_file = showcase_client
    before = config_file.read_text(encoding="utf-8")

    rc = client.post(SHOWCASE_URI, json={"label": unsafe_label}, headers=_admin_headers())

    assert rc.status_code == 422
    # Nothing was written when the input is refused.
    assert config_file.read_text(encoding="utf-8") == before


def test_showcase_admin_post_rejects_non_string_label(showcase_client):
    _, client, _ = showcase_client

    rc = client.post(SHOWCASE_URI, json={"label": 123}, headers=_admin_headers())

    assert rc.status_code == 422


def test_showcase_admin_post_forbidden_without_config_edit(showcase_client):
    ftbot, client, config_file = showcase_client
    before = config_file.read_text(encoding="utf-8")
    ftbot.config["ck_quant_admin"]["config_edit"] = False

    get_rc = client.get(SHOWCASE_URI, headers=_admin_headers())
    post_rc = client.post(SHOWCASE_URI, json={"enabled": True}, headers=_admin_headers())

    assert get_rc.status_code == 403
    assert post_rc.status_code == 403
    assert config_file.read_text(encoding="utf-8") == before


def test_showcase_admin_hidden_when_admin_disabled(showcase_client):
    ftbot, client, _ = showcase_client
    ftbot.config["ck_quant_admin"]["enabled"] = False

    rc = client.get(SHOWCASE_URI, headers=_admin_headers())

    assert rc.status_code == 404


def test_showcase_admin_post_without_config_file_is_rejected(showcase_client, mocker):
    """Without an editable config file the write must fail loudly, not silently."""
    ftbot, client, _ = showcase_client
    mocker.patch(
        "freqtrade.rpc.rpc.RPC._rpc_reload_config",
        MagicMock(return_value={"status": "Reloading config ..."}),
    )
    ftbot.config["config_files"] = []

    rc = client.post(SHOWCASE_URI, json={"enabled": True}, headers=_admin_headers())

    assert rc.status_code == 409
