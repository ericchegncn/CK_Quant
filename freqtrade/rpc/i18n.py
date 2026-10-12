# pragma pylint: disable=too-few-public-methods

"""
Localization (i18n) helpers for user facing bot messages.

Every user facing string sent by the bots (telegram, ...) is built from a
translation key.  The English catalogue is the source of truth and lives in
``freqtrade/rpc/locales/<area>.en.json`` - one small JSON fragment per area
(``tg`` = telegram messages, ``rpc`` = errors raised by the RPC layer and
shown in the chat).  Additional languages simply add
``<area>.<locale>.json`` next to it; missing keys fall back to English.

The default locale is ``en``: with ``telegram.language = "en"`` (or the key
absent) the produced text is byte identical to the pre-i18n output, which
keeps the upstream test suite meaningful.

Locale resolution order for a chat:

1. per chat override set with ``/language`` (persisted in
   ``<user_data_dir>/bot_languages.json`` so it survives restarts),
2. ``telegram.language`` from the config,
3. ``en``.

Supported locales mirror the WebUI picker (``ck_quant_ui/src/i18n/index.ts``).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"

DEFAULT_LOCALE = "en"

# Keep in sync with ck_quant_ui/src/i18n/index.ts (supportedLocales).
SUPPORTED_LOCALES: tuple[str, ...] = ("en", "zh-CN", "zh-TW", "de", "ja", "fr", "ko")

# Language pickers always show the native name of the target language.
NATIVE_LOCALE_NAMES: dict[str, str] = {
    "en": "English",
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "de": "Deutsch",
    "ja": "日本語",
    "fr": "Français",
    "ko": "한국어",
}

# File holding the per chat language overrides (inside user_data_dir).
STATE_FILENAME = "bot_languages.json"

_LOCALE_ALIASES: dict[str, str] = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
    "zh-sg": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hk": "zh-TW",
    "zh-mo": "zh-TW",
    "zh-hant": "zh-TW",
    "jp": "ja",
    "ja-jp": "ja",
    "kr": "ko",
    "ko-kr": "ko",
    "en-us": "en",
    "en-gb": "en",
}


def normalize_locale(value: str | None) -> str | None:
    """Return the canonical locale code for ``value``, or None when unknown."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    low = raw.replace("_", "-").lower()
    if low in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[low]
    for code in SUPPORTED_LOCALES:
        if low == code.lower():
            return code
    for code in SUPPORTED_LOCALES:
        base = code.split("-")[0].lower()
        if base == "zh":
            # zh variants are only reachable through the alias table above.
            continue
        if low == base or low.startswith(f"{base}-"):
            return code
    return None


def available_locales() -> tuple[str, ...]:
    """Locales accepted by the bot (canonical codes)."""
    return SUPPORTED_LOCALES


def locale_name(code: str) -> str:
    """Native name of a locale code (falls back to the code itself)."""
    return NATIVE_LOCALE_NAMES.get(code, code)


class I18n:
    """
    Translation catalogue with a per chat locale override.

    Thread safe: telegram handlers run in their own thread while the config
    file is owned by the main thread.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        state_path: Path | str | None = None,
        locales_dir: Path | str | None = None,
        default_locale: str | None = None,
    ) -> None:
        self._lock = Lock()
        self._locales_dir = Path(locales_dir) if locales_dir else LOCALES_DIR
        self._cache: dict[str, dict[str, str]] = {}
        self._chat_locales: dict[str, str] = {}
        self._state_path = Path(state_path) if state_path else None

        configured: str | None = None
        if config:
            configured = (config.get("telegram") or {}).get("language")
            if configured and normalize_locale(configured) is None:
                logger.warning(
                    "Invalid telegram.language '%s' - falling back to '%s'.",
                    configured,
                    DEFAULT_LOCALE,
                )
            if self._state_path is None:
                user_data_dir = config.get("user_data_dir")
                if user_data_dir:
                    self._state_path = Path(user_data_dir) / STATE_FILENAME

        self._default_locale = (
            normalize_locale(default_locale)
            or normalize_locale(configured)
            or DEFAULT_LOCALE
        )
        self._load_state()

    # ------------------------------------------------------------------ catalog
    def _load_fragment(self, area: str, locale: str) -> dict[str, str]:
        path = self._locales_dir / f"{area}.{locale}.json"
        if not path.is_file():
            return {}
        try:
            with path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.warning("Could not load locale fragment %s: %s", path, exc)
            return {}
        if not isinstance(data, dict):
            logger.warning("Locale fragment %s must contain a JSON object.", path)
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def messages(self, locale: str | None = None) -> dict[str, str]:
        """
        Merged catalogue for ``locale`` (English fragments first, then the
        locale specific overrides).
        """
        code = normalize_locale(locale) or self._default_locale
        with self._lock:
            cached = self._cache.get(code)
            if cached is not None:
                return cached
        merged: dict[str, str] = {}
        areas = sorted(
            {path.name.rsplit(".", 2)[0] for path in self._locales_dir.glob(f"*.{DEFAULT_LOCALE}.json")}
        )
        for area in areas:
            merged.update(self._load_fragment(area, DEFAULT_LOCALE))
        if code != DEFAULT_LOCALE:
            for area in sorted(
                {path.name.rsplit(".", 2)[0] for path in self._locales_dir.glob(f"*.{code}.json")}
            ):
                merged.update(self._load_fragment(area, code))
        with self._lock:
            self._cache[code] = merged
        return merged

    def has_key(self, key: str, locale: str | None = None) -> bool:
        return key in self.messages(locale)

    # --------------------------------------------------------------- translator
    @property
    def default_locale(self) -> str:
        return self._default_locale

    def locale_for(self, chat_id: int | str | None = None) -> str:
        """Effective locale of a chat (falls back to the configured default)."""
        if chat_id is None:
            return self._default_locale
        with self._lock:
            return self._chat_locales.get(str(chat_id), self._default_locale)

    def t(
        self,
        key: str,
        *,
        chat_id: int | str | None = None,
        locale: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Translate ``key`` using the locale of ``chat_id`` (or an explicit
        ``locale``) and interpolate ``kwargs``.
        """
        code = normalize_locale(locale) or self.locale_for(chat_id)
        catalogue = self.messages(code)
        template = catalogue.get(key)
        if template is None:
            logger.warning("Missing translation for key '%s' (%s).", key, code)
            return key
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("Bad placeholders for key '%s' (%s): %s", key, code, exc)
            return template

    # ------------------------------------------------------------ chat overrides
    def set_locale(self, chat_id: int | str, value: str) -> str | None:
        """
        Persist the language of ``chat_id``.  Returns the canonical code, or
        None when ``value`` is not a supported language.
        """
        code = normalize_locale(value)
        if code is None:
            return None
        with self._lock:
            self._chat_locales[str(chat_id)] = code
            self._save_state_locked()
        return code

    def locale_choices(self, chat_id: int | str | None = None) -> list[tuple[str, str, bool]]:
        """``(code, native name, is_current)`` for the language picker."""
        current = self.locale_for(chat_id)
        return [(code, locale_name(code), code == current) for code in SUPPORTED_LOCALES]

    # ---------------------------------------------------------------- state file
    def _load_state(self) -> None:
        if self._state_path is None or not self._state_path.is_file():
            return
        try:
            with self._state_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            logger.warning("Could not read language state %s: %s", self._state_path, exc)
            return
        chats = data.get("chats") if isinstance(data, dict) else None
        if not isinstance(chats, dict):
            return
        loaded: dict[str, str] = {}
        for chat_id, value in chats.items():
            code = normalize_locale(value)
            if code:
                loaded[str(chat_id)] = code
        with self._lock:
            self._chat_locales.update(loaded)

    def _save_state_locked(self) -> None:
        if self._state_path is None:
            return
        payload = {"chats": dict(self._chat_locales)}
        tmp = self._state_path.with_suffix(".json.tmp")
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(tmp, self._state_path)
        except OSError as exc:
            logger.warning("Could not persist language state %s: %s", self._state_path, exc)
