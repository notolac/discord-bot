"""Thin shared library for Discord HTTP-interactions bots."""

from discord_core.app import create_app
from discord_core.cli import run_cli
from discord_core.http import DiscordAPIError, DiscordClient
from discord_core.router import InteractionContext, Router
from discord_core.settings import DiscordSettings

__all__ = [
    "DiscordAPIError",
    "DiscordClient",
    "DiscordSettings",
    "InteractionContext",
    "Router",
    "create_app",
    "run_cli",
]

__version__ = "0.1.0"
