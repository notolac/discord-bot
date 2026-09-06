"""ASGI factory for ``uvicorn --reload`` (import string, not an app object)."""

from bot_template import BOT_NAME, BOT_ROOT
from bot_template.handlers import router
from bot_template.settings import Settings
from fastapi import FastAPI

from discord_core.app import create_app
from discord_core.logging import configure_logging


def app() -> FastAPI:
    """Build the Bot Template FastAPI app (reloader child process)."""
    settings = Settings()  # type: ignore[call-arg]
    if settings.log_dir is None:
        settings.log_dir = BOT_ROOT / "logs"
    if settings.i18n_dir is None:
        settings.i18n_dir = BOT_ROOT / "i18n"
    settings.bot_name = BOT_NAME
    configure_logging(settings.log_level, log_dir=settings.log_dir, name=BOT_NAME)
    return create_app(settings, router)
