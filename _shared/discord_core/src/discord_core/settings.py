"""Base settings shared by every bot (environment / ``.env``).

Values come from the Developer Portal — see ``docs/developer-portal.md``. Bots subclass
``DiscordSettings`` to add their own variables (prefix them with the bot name).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordSettings(BaseSettings):
    """Common configuration. Every field maps 1:1 to an upper-case env var."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_app_id: str = Field(description="Application ID (General Information page)")
    discord_public_key: str = Field(description="Public Key used to verify interaction signatures")
    discord_bot_token: SecretStr = Field(description="Bot token (Bot page › Reset Token)")
    discord_dev_guild_id: str | None = Field(
        default=None, description="Test server id; guild commands are registered here in dev"
    )

    bot_name: str = Field(default="bot", description="Used for log file names and User-Agent")
    bot_version: str = Field(default="0.1.0")
    default_locale: str = Field(default="en-US")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    log_dir: Path | None = Field(
        default=None,
        description="Directory for rotating log files (bot's logs/); None = stdout only",
    )
    i18n_dir: Path | None = Field(default=None, description="Directory with <locale>.json tables")
