"""Odin settings (env vars prefixed ``ODIN_``)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from discord_core import DiscordSettings
from odin import BOT_ROOT


class Settings(DiscordSettings):
    """Environment configuration for Odin."""

    odin_mod_channel_id: str | None = Field(
        default=None, description="Channel receiving reports and moderation notices"
    )
    odin_reports_dir: Path = Field(
        default=BOT_ROOT / "reports", description="Directory for the moderation JSONL log"
    )
    odin_history_limit: int = Field(
        default=10, ge=1, le=25, description="Entries shown by View history"
    )
