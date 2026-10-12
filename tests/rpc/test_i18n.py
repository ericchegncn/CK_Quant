"""
Tests for the bot localization helpers (freqtrade/rpc/i18n.py).
"""

import json
import re
from pathlib import Path

import pytest

from freqtrade.rpc.i18n import (
    DEFAULT_LOCALE,
    LOCALES_DIR,
    SUPPORTED_LOCALES,
    I18n,
    available_locales,
    locale_name,
    normalize_locale,
)

PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")


def _fragments(locales_dir: Path) -> dict[str, dict[str, str]]:
    """``{locale: {key: value}}`` for every shipped fragment file."""
    result: dict[str, dict[str, str]] = {}
    for path in sorted(locales_dir.glob("*.json")):
        parts = path.name.split(".")
        if len(parts) != 3 or parts[2] != "json":
            continue
        locale = parts[1]
        data = json.loads(path.read_text(encoding="utf-8"))
        catalogue = result.setdefault(locale, {})
        for key, value in data.items():
            assert key not in catalogue, f"duplicate key {key} ({path.name})"
            catalogue[key] = value
    return result


@pytest.mark.parametrize(
    "value,expected",
    [
        ("en", "en"),
        ("EN", "en"),
        ("en-US", "en"),
        ("zh", "zh-CN"),
        ("zh_CN", "zh-CN"),
        ("zh-Hans", "zh-CN"),
        ("zh-TW", "zh-TW"),
        ("zh-hant", "zh-TW"),
        ("zh-HK", "zh-TW"),
        ("de", "de"),
        ("fr", "fr"),
        ("ja", "ja"),
        ("jp", "ja"),
        ("ko", "ko"),
        ("kr", "ko"),
        ("klingon", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_locale(value, expected) -> None:
    assert normalize_locale(value) == expected


def test_supported_locales_match_ui_picker() -> None:
    assert available_locales() == SUPPORTED_LOCALES
    assert DEFAULT_LOCALE in SUPPORTED_LOCALES
    for code in SUPPORTED_LOCALES:
        # every locale has a native name (language pickers show those)
        assert locale_name(code)


def test_translate_and_fallback(tmp_path: Path) -> None:
    (tmp_path / "tg.en.json").write_text(
        json.dumps({"tg.hello": "Hello {name}", "tg.only_en": "English only"}),
        encoding="utf-8",
    )
    (tmp_path / "tg.zh-CN.json").write_text(
        json.dumps({"tg.hello": "你好 {name}"}), encoding="utf-8"
    )
    i18n = I18n({"telegram": {"language": "zh-CN"}}, locales_dir=tmp_path)

    assert i18n.default_locale == "zh-CN"
    assert i18n.t("tg.hello", name="BTC") == "你好 BTC"
    # untranslated keys fall back to the English source
    assert i18n.t("tg.only_en") == "English only"
    # unknown keys are returned as-is (never crash a running bot)
    assert i18n.t("tg.missing") == "tg.missing"


def test_translate_bad_placeholder_does_not_raise(tmp_path: Path) -> None:
    (tmp_path / "tg.en.json").write_text(
        json.dumps({"tg.hello": "Hello {name}"}), encoding="utf-8"
    )
    i18n = I18n({}, locales_dir=tmp_path)
    assert i18n.t("tg.hello") == "Hello {name}"


def test_invalid_config_language_falls_back(tmp_path: Path) -> None:
    i18n = I18n({"telegram": {"language": "klingon"}}, locales_dir=tmp_path)
    assert i18n.default_locale == "en"


def test_per_chat_override_persists(tmp_path: Path) -> None:
    state = tmp_path / "bot_languages.json"
    locales = tmp_path / "locales"
    locales.mkdir()
    (locales / "tg.en.json").write_text(json.dumps({"tg.hello": "Hello"}), encoding="utf-8")
    (locales / "tg.de.json").write_text(json.dumps({"tg.hello": "Hallo"}), encoding="utf-8")

    config = {"telegram": {"language": "en"}}
    i18n = I18n(config, locales_dir=locales, state_path=state)
    assert i18n.locale_for(123) == "en"
    assert i18n.t("tg.hello", chat_id=123) == "Hello"

    assert i18n.set_locale(123, "de-DE") == "de"
    assert i18n.t("tg.hello", chat_id=123) == "Hallo"
    # a different chat keeps the configured default
    assert i18n.t("tg.hello", chat_id=999) == "Hello"
    # unsupported values are rejected (and not persisted)
    assert i18n.set_locale(123, "klingon") is None
    assert i18n.t("tg.hello", chat_id=123) == "Hallo"

    reloaded = I18n(config, locales_dir=locales, state_path=state)
    assert reloaded.locale_for(123) == "de"
    assert json.loads(state.read_text(encoding="utf-8")) == {"chats": {"123": "de"}}


def test_locale_choices_marks_current(tmp_path: Path) -> None:
    i18n = I18n({"telegram": {"language": "ja"}}, locales_dir=tmp_path, state_path=None)
    choices = i18n.locale_choices(1)
    assert [code for code, _, _ in choices] == list(SUPPORTED_LOCALES)
    assert [code for code, _, current in choices if current] == ["ja"]


def test_state_file_corrupt_is_ignored(tmp_path: Path) -> None:
    state = tmp_path / "bot_languages.json"
    state.write_text("{not json", encoding="utf-8")
    i18n = I18n({"telegram": {"language": "fr"}}, locales_dir=tmp_path, state_path=state)
    assert i18n.default_locale == "fr"
    assert i18n.locale_for(1) == "fr"


# --------------------------------------------------------------- shipped files
def test_shipped_catalogue_files_are_valid() -> None:
    """Every shipped fragment must be a flat JSON object of strings."""
    files = sorted(LOCALES_DIR.glob("*.json"))
    assert files, "no locale fragments found"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), path
        for key, value in data.items():
            assert isinstance(key, str) and "." in key, (path, key)
            assert isinstance(value, str) and value, (path, key)


def test_every_shipped_locale_translates_every_key() -> None:
    """
    All supported locales must cover the full English catalogue - a partial
    translation would silently mix languages in the chat.
    """
    fragments = _fragments(LOCALES_DIR)
    english = fragments[DEFAULT_LOCALE]
    for locale in SUPPORTED_LOCALES:
        assert locale in fragments, f"missing locale fragment for {locale}"
        missing = sorted(set(english) - set(fragments[locale]))
        extra = sorted(set(fragments[locale]) - set(english))
        assert not missing, f"{locale} misses keys: {missing}"
        assert not extra, f"{locale} has unknown keys: {extra}"


def test_placeholders_match_english() -> None:
    """A translation must use exactly the same placeholder names as English."""
    fragments = _fragments(LOCALES_DIR)
    english = fragments[DEFAULT_LOCALE]
    for locale, catalogue in fragments.items():
        for key, value in catalogue.items():
            if key not in english:
                continue
            expected = set(PLACEHOLDER_RE.findall(english[key]))
            found = set(PLACEHOLDER_RE.findall(value))
            assert found == expected, (
                f"{locale}:{key} placeholders {sorted(found)} != {sorted(expected)}"
            )
