"""Locale string tables.

Policy (see PLAN §1.4): code and default strings are English (``en-US``); other locales live in
``<bot>/i18n/<locale>.json`` as flat ``{"key": "text"}`` maps. Discord locale codes:
https://docs.discord.com/developers/reference#locales
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LOCALE = "en-US"

# Strings the core itself needs. Bots may override any key in their own tables.
_CORE_STRINGS: dict[str, dict[str, str]] = {
    "en-US": {
        "core.unknown_interaction": "Sorry, I do not know how to handle that.",
        "core.internal_error": "Something went wrong while processing your request.",
    },
    "es-ES": {
        "core.unknown_interaction": "Lo siento, no sé cómo gestionar esa acción.",
        "core.internal_error": "Algo ha fallado al procesar tu solicitud.",
    },
}


class Localizer:
    """Lookup of translated strings with fallback to the default locale."""

    def __init__(
        self, tables: dict[str, dict[str, str]] | None = None, default: str = DEFAULT_LOCALE
    ):
        self.default = default
        self._tables: dict[str, dict[str, str]] = {
            locale: dict(strings) for locale, strings in _CORE_STRINGS.items()
        }
        for locale, strings in (tables or {}).items():
            self._tables.setdefault(locale, {}).update(strings)

    @classmethod
    def from_dir(cls, directory: Path | None, default: str = DEFAULT_LOCALE) -> Localizer:
        """Load every ``<locale>.json`` file in ``directory`` (missing dir → core strings only)."""
        tables: dict[str, dict[str, str]] = {}
        if directory is not None and directory.is_dir():
            for path in sorted(directory.glob("*.json")):
                with path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    msg = f"{path}: locale table must be a JSON object"
                    raise TypeError(msg)
                tables[path.stem] = {str(k): str(v) for k, v in data.items()}
        return cls(tables, default=default)

    @property
    def locales(self) -> list[str]:
        """Locales with at least one string."""
        return sorted(self._tables)

    def t(self, key: str, *, locale: str | None = None, **kwargs: Any) -> str:
        """Translate ``key`` for ``locale`` (fallback: default locale, then the key itself)."""
        for candidate in (locale, self.default):
            if candidate and key in self._tables.get(candidate, {}):
                return (
                    self._tables[candidate][key].format(**kwargs)
                    if kwargs
                    else self._tables[candidate][key]
                )
        return key

    def localizations(self, key: str) -> dict[str, str] | None:
        """Build a ``name_localizations``-style dict for ``key`` (all locales but the default)."""
        result = {
            locale: strings[key]
            for locale, strings in self._tables.items()
            if locale != self.default and key in strings
        }
        return result or None
