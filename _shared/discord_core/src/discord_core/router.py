"""Dispatch incoming interactions to handlers.

* ``APPLICATION_COMMAND`` → handler registered by top-level command name.
* ``APPLICATION_COMMAND_AUTOCOMPLETE`` → autocomplete handler by command name.
* ``MESSAGE_COMPONENT`` / ``MODAL_SUBMIT`` → handler whose ``custom_id`` prefix matches
  (longest prefix wins).

Handlers are ``async def handler(interaction, ctx) -> dict`` and must return an interaction
response payload. Discord requires that payload within **3 seconds**; handlers declared with
``defer=True`` get an automatic deferred ACK and run afterwards in the background, then their
return value is sent through *edit original response*.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

from discord_core import responses
from discord_core.interactions import Interaction, InteractionType

if TYPE_CHECKING:
    from discord_core.http import DiscordClient
    from discord_core.i18n import Localizer
    from discord_core.settings import DiscordSettings


@dataclass(slots=True)
class InteractionContext:
    """Per-request context handed to handlers."""

    settings: DiscordSettings
    client: DiscordClient
    i18n: Localizer
    log: Any = field(default_factory=lambda: structlog.get_logger("discord_core"))

    def t(self, key: str, interaction: Interaction | None = None, **kwargs: Any) -> str:
        """Translate ``key`` using the invoking user's locale (falls back to default)."""
        locale = interaction.locale if interaction is not None else None
        return self.i18n.t(key, locale=locale, **kwargs)


Handler = Callable[[Interaction, InteractionContext], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class _Registration:
    handler: Handler
    defer: bool = False
    ephemeral: bool = False


@dataclass(slots=True)
class DispatchResult:
    """Immediate response plus an optional background coroutine to run after replying."""

    response: dict[str, Any]
    background: Awaitable[None] | None = None


class Router:
    """Registry of interaction handlers."""

    def __init__(self) -> None:
        self._commands: dict[str, _Registration] = {}
        self._autocomplete: dict[str, Handler] = {}
        self._components: dict[str, _Registration] = {}
        self._modals: dict[str, _Registration] = {}
        self._log = structlog.get_logger("discord_core.router")

    # --------------------------------------------------------------- decorators

    def command(
        self, name: str, *, defer: bool = False, ephemeral: bool = False
    ) -> Callable[[Handler], Handler]:
        """Register a handler for the top-level command ``name`` (any command type)."""

        def decorator(func: Handler) -> Handler:
            if name in self._commands:
                msg = f"command handler already registered: {name!r}"
                raise ValueError(msg)
            self._commands[name] = _Registration(func, defer=defer, ephemeral=ephemeral)
            return func

        return decorator

    def autocomplete(self, name: str) -> Callable[[Handler], Handler]:
        """Register the autocomplete handler for command ``name``."""

        def decorator(func: Handler) -> Handler:
            self._autocomplete[name] = func
            return func

        return decorator

    def component(
        self, custom_id_prefix: str, *, defer: bool = False, ephemeral: bool = False
    ) -> Callable[[Handler], Handler]:
        """Register a handler for message components whose ``custom_id`` starts with the prefix."""

        def decorator(func: Handler) -> Handler:
            self._components[custom_id_prefix] = _Registration(
                func, defer=defer, ephemeral=ephemeral
            )
            return func

        return decorator

    def modal(
        self, custom_id_prefix: str, *, defer: bool = False, ephemeral: bool = False
    ) -> Callable[[Handler], Handler]:
        """Register a handler for modal submits whose ``custom_id`` starts with the prefix."""

        def decorator(func: Handler) -> Handler:
            self._modals[custom_id_prefix] = _Registration(func, defer=defer, ephemeral=ephemeral)
            return func

        return decorator

    def include(self, other: Router) -> None:
        """Merge another router's registrations into this one (fails on duplicate names)."""
        for name, reg in other._commands.items():
            if name in self._commands:
                msg = f"duplicate command handler on include: {name!r}"
                raise ValueError(msg)
            self._commands[name] = reg
        self._autocomplete.update(other._autocomplete)
        self._components.update(other._components)
        self._modals.update(other._modals)

    # ----------------------------------------------------------------- dispatch

    async def dispatch(self, interaction: Interaction, ctx: InteractionContext) -> DispatchResult:
        """Route ``interaction`` and return the immediate response (+ background work)."""
        if interaction.type == InteractionType.PING:
            return DispatchResult(responses.pong())

        if interaction.type == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            handler = self._autocomplete.get(interaction.command_name or "")
            if handler is None:
                return DispatchResult(responses.autocomplete([]))
            return DispatchResult(await handler(interaction, ctx))

        registration = self._resolve(interaction)
        if registration is None:
            ctx.log.warning(
                "unhandled_interaction",
                type=int(interaction.type),
                name=interaction.command_name,
                custom_id=interaction.custom_id,
            )
            return DispatchResult(
                responses.ephemeral(ctx.t("core.unknown_interaction", interaction))
            )

        if not registration.defer:
            return DispatchResult(await registration.handler(interaction, ctx))

        # Deferred path: ACK now, run handler afterwards, then edit the original response.
        is_component = interaction.type == InteractionType.MESSAGE_COMPONENT
        ack = (
            responses.deferred_update()
            if is_component and not registration.ephemeral
            else responses.deferred(ephemeral=registration.ephemeral)
        )
        return DispatchResult(ack, self._run_deferred(registration.handler, interaction, ctx))

    def _resolve(self, interaction: Interaction) -> _Registration | None:
        if interaction.type == InteractionType.APPLICATION_COMMAND:
            return self._commands.get(interaction.command_name or "")
        table = (
            self._components
            if interaction.type == InteractionType.MESSAGE_COMPONENT
            else self._modals
        )
        custom_id = interaction.custom_id or ""
        matches = [prefix for prefix in table if custom_id.startswith(prefix)]
        if not matches:
            return None
        return table[max(matches, key=len)]

    async def _run_deferred(
        self, handler: Handler, interaction: Interaction, ctx: InteractionContext
    ) -> None:
        try:
            result = await handler(interaction, ctx)
        except Exception:
            ctx.log.exception("deferred_handler_failed", name=interaction.command_name)
            result = responses.ephemeral(ctx.t("core.internal_error", interaction))
        data = result.get("data", result)
        try:
            await ctx.client.edit_original_response(
                interaction.application_id, interaction.token, data
            )
        except Exception:
            ctx.log.exception("edit_original_failed", name=interaction.command_name)

    # ----------------------------------------------------------------- helpers

    @property
    def command_names(self) -> list[str]:
        """Registered top-level command names (for CLI listing / consistency checks)."""
        return sorted(self._commands)


def schedule(background: Awaitable[None] | None) -> asyncio.Task[None] | None:
    """Fire-and-forget a background coroutine on the running loop (keeps a reference)."""
    if background is None:
        return None
    task = asyncio.ensure_future(background)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()
