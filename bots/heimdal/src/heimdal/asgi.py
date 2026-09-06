"""ASGI factory for ``uvicorn --reload`` (import string, not an app object)."""

from fastapi import FastAPI

from discord_core.app import create_app
from discord_core.logging import configure_logging
from heimdal import BOT_NAME, BOT_ROOT
from heimdal.handlers import router
from heimdal.settings import Settings


def app() -> FastAPI:
    """Build the Heimdal FastAPI app (reloader child process)."""
    settings = Settings()  # type: ignore[call-arg]
    if settings.log_dir is None:
        settings.log_dir = BOT_ROOT / "logs"
    if settings.i18n_dir is None:
        settings.i18n_dir = BOT_ROOT / "i18n"
    settings.bot_name = BOT_NAME
    configure_logging(settings.log_level, log_dir=settings.log_dir, name=BOT_NAME)
    return create_app(settings, router)
