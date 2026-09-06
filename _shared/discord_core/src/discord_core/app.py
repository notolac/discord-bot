"""FastAPI application factory exposing the Interactions Endpoint.

``POST /interactions``
    1. Verify ``X-Signature-Ed25519`` / ``X-Signature-Timestamp`` → 401 on failure.
    2. Answer ``PING`` with ``PONG``.
    3. Dispatch through the router; schedule deferred work after replying.

``GET /healthz``
    Liveness probe for reverse proxies / orchestrators.

Reference: https://docs.discord.com/developers/interactions/overview#preparing-for-interactions
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from discord_core.http import DiscordClient
from discord_core.i18n import Localizer
from discord_core.interactions import Interaction, InteractionType
from discord_core.responses import pong
from discord_core.router import InteractionContext, Router, schedule
from discord_core.security import SIGNATURE_HEADER, TIMESTAMP_HEADER, verify_signature
from discord_core.settings import DiscordSettings


def create_app(
    settings: DiscordSettings,
    router: Router,
    *,
    client: DiscordClient | None = None,
    localizer: Localizer | None = None,
) -> FastAPI:
    """Build the FastAPI app for one bot.

    ``client`` and ``localizer`` can be injected for tests; otherwise they are created from
    ``settings`` during the lifespan.
    """
    log = structlog.get_logger("discord_core.app")
    i18n = localizer or Localizer.from_dir(settings.i18n_dir, default=settings.default_locale)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = client is None
        app.state.client = client or DiscordClient(
            settings.discord_bot_token.get_secret_value(), version=settings.bot_version
        )
        log.info("bot_started", bot=settings.bot_name, app_id=settings.discord_app_id)
        try:
            yield
        finally:
            if owned:
                await app.state.client.aclose()
            log.info("bot_stopped", bot=settings.bot_name)

    app = FastAPI(title=f"{settings.bot_name} interactions", lifespan=lifespan, docs_url=None)
    app.state.settings = settings
    app.state.router = router

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "bot": settings.bot_name, "version": settings.bot_version}

    @app.post("/interactions")
    async def interactions(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get(SIGNATURE_HEADER, "")
        timestamp = request.headers.get(TIMESTAMP_HEADER, "")
        if not verify_signature(settings.discord_public_key, signature, timestamp, body):
            log.warning("invalid_signature", remote=request.client.host if request.client else None)
            return JSONResponse({"error": "invalid request signature"}, status_code=401)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)

        if payload.get("type") == InteractionType.PING:
            return JSONResponse(pong())

        try:
            interaction = Interaction.model_validate(payload)
        except ValidationError as exc:
            log.warning("invalid_interaction", errors=exc.errors())
            return JSONResponse({"error": "invalid interaction payload"}, status_code=400)

        structlog.contextvars.bind_contextvars(
            interaction_id=interaction.id,
            interaction_type=int(interaction.type),
            command=interaction.command_name,
            custom_id=interaction.custom_id,
            guild_id=interaction.guild_id,
        )
        ctx = InteractionContext(settings=settings, client=request.app.state.client, i18n=i18n)
        try:
            result = await router.dispatch(interaction, ctx)
        except Exception:
            log.exception("handler_failed")
            structlog.contextvars.clear_contextvars()
            return JSONResponse(
                {
                    "type": 4,
                    "data": {
                        "content": i18n.t("core.internal_error", locale=interaction.locale),
                        "flags": 64,
                    },
                }
            )
        structlog.contextvars.clear_contextvars()
        schedule(result.background)
        return JSONResponse(result.response)

    return app
