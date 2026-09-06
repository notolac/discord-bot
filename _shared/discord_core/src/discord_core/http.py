"""Minimal async client for the Discord HTTP API v10.

Implements the mandatory bits from https://docs.discord.com/developers/reference :
* base URL with explicit version, ``Authorization: Bot <token>``,
* a valid ``User-Agent: DiscordBot ($url, $version)``,
* ``Content-Type: application/json``,
* rate-limit handling (HTTP 429 → wait ``retry_after`` and retry),
* structured error surface for ``50035``-style bodies.
"""

from __future__ import annotations

import asyncio
from typing import Any, Self

import httpx

API_BASE_URL = "https://discord.com/api/v10"
REPO_URL = "https://github.com/notolac/discord-bot"


class DiscordAPIError(Exception):
    """Non-2xx response from the Discord API."""

    def __init__(self, status: int, body: Any, *, method: str, path: str) -> None:
        self.status = status
        self.body = body
        self.method = method
        self.path = path
        self.code: int | None = body.get("code") if isinstance(body, dict) else None
        self.message: str = body.get("message", "") if isinstance(body, dict) else str(body)[:200]
        self.errors: Any = body.get("errors") if isinstance(body, dict) else None
        super().__init__(f"{method} {path} -> {status} {self.code}: {self.message}")


class DiscordClient:
    """Async HTTP client bound to one bot token. Use as an async context manager."""

    def __init__(
        self,
        bot_token: str,
        *,
        version: str = "0.1.0",
        base_url: str = API_BASE_URL,
        timeout: float = 10.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"Bot {bot_token}",
                "User-Agent": f"DiscordBot ({REPO_URL}, {version})",
            },
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------- transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> Any:
        """Perform a request, retrying on 429. Returns the decoded JSON (or ``None`` on 204)."""
        headers: dict[str, str] = {}
        if reason:
            headers["X-Audit-Log-Reason"] = reason
        attempt = 0
        while True:
            response = await self._client.request(
                method, path, json=json, params=params, headers=headers
            )
            if response.status_code == 429 and attempt < self._max_retries:
                attempt += 1
                await asyncio.sleep(_retry_after_seconds(response))
                continue
            if response.is_success and (response.status_code == 204 or not response.content):
                return None
            body = _safe_json(response)
            if not response.is_success:
                raise DiscordAPIError(response.status_code, body, method=method, path=path)
            return body

    # -------------------------------------------------- application commands

    async def get_global_commands(self, application_id: str) -> list[dict[str, Any]]:
        """``GET /applications/{app}/commands``."""
        return await self.request("GET", f"/applications/{application_id}/commands")

    async def put_global_commands(
        self, application_id: str, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """``PUT /applications/{app}/commands`` — bulk overwrite (deletes missing ones)."""
        return await self.request("PUT", f"/applications/{application_id}/commands", json=commands)

    async def get_guild_commands(self, application_id: str, guild_id: str) -> list[dict[str, Any]]:
        """``GET /applications/{app}/guilds/{guild}/commands``."""
        return await self.request(
            "GET", f"/applications/{application_id}/guilds/{guild_id}/commands"
        )

    async def put_guild_commands(
        self, application_id: str, guild_id: str, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """``PUT /applications/{app}/guilds/{guild}/commands`` — bulk overwrite."""
        return await self.request(
            "PUT", f"/applications/{application_id}/guilds/{guild_id}/commands", json=commands
        )

    # ------------------------------------------------------- interactions

    async def create_interaction_response(
        self, interaction_id: str, token: str, payload: dict[str, Any]
    ) -> None:
        """``POST /interactions/{id}/{token}/callback`` (needed when receiving via Gateway)."""
        await self.request("POST", f"/interactions/{interaction_id}/{token}/callback", json=payload)

    async def edit_original_response(
        self, application_id: str, token: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """``PATCH /webhooks/{app}/{token}/messages/@original``."""
        return await self.request(
            "PATCH", f"/webhooks/{application_id}/{token}/messages/@original", json=data
        )

    async def delete_original_response(self, application_id: str, token: str) -> None:
        """``DELETE /webhooks/{app}/{token}/messages/@original``."""
        await self.request("DELETE", f"/webhooks/{application_id}/{token}/messages/@original")

    async def create_followup(
        self, application_id: str, token: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """``POST /webhooks/{app}/{token}`` — follow-up message (token valid 15 min)."""
        return await self.request("POST", f"/webhooks/{application_id}/{token}", json=data)

    # ------------------------------------------------------------- guilds

    async def add_member_role(
        self, guild_id: str, user_id: str, role_id: str, *, reason: str | None = None
    ) -> None:
        """``PUT /guilds/{guild}/members/{user}/roles/{role}`` (needs ``MANAGE_ROLES``)."""
        await self.request(
            "PUT", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", reason=reason
        )

    async def remove_member_role(
        self, guild_id: str, user_id: str, role_id: str, *, reason: str | None = None
    ) -> None:
        """``DELETE /guilds/{guild}/members/{user}/roles/{role}``."""
        await self.request(
            "DELETE", f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}", reason=reason
        )

    async def modify_guild_member(
        self, guild_id: str, user_id: str, data: dict[str, Any], *, reason: str | None = None
    ) -> dict[str, Any]:
        """``PATCH /guilds/{guild}/members/{user}`` (e.g. ``communication_disabled_until``)."""
        return await self.request(
            "PATCH", f"/guilds/{guild_id}/members/{user_id}", json=data, reason=reason
        )

    # ----------------------------------------------------------- channels

    async def create_message(self, channel_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """``POST /channels/{channel}/messages``."""
        return await self.request("POST", f"/channels/{channel_id}/messages", json=data)

    async def get_channel_messages(
        self, channel_id: str, *, limit: int = 50, before: str | None = None
    ) -> list[dict[str, Any]]:
        """``GET /channels/{channel}/messages`` (1–100)."""
        params: dict[str, Any] = {"limit": max(1, min(limit, 100))}
        if before:
            params["before"] = before
        return await self.request("GET", f"/channels/{channel_id}/messages", params=params)

    async def delete_message(
        self, channel_id: str, message_id: str, *, reason: str | None = None
    ) -> None:
        """``DELETE /channels/{channel}/messages/{message}``."""
        await self.request("DELETE", f"/channels/{channel_id}/messages/{message_id}", reason=reason)

    async def bulk_delete_messages(
        self, channel_id: str, message_ids: list[str], *, reason: str | None = None
    ) -> None:
        """``POST /channels/{channel}/messages/bulk-delete`` (2–100 ids, < 14 days old)."""
        if len(message_ids) == 1:
            await self.delete_message(channel_id, message_ids[0], reason=reason)
            return
        await self.request(
            "POST",
            f"/channels/{channel_id}/messages/bulk-delete",
            json={"messages": message_ids},
            reason=reason,
        )


def _retry_after_seconds(response: httpx.Response) -> float:
    body = _safe_json(response)
    if isinstance(body, dict) and "retry_after" in body:
        try:
            return float(body["retry_after"])
        except TypeError, ValueError:
            pass
    header = response.headers.get("Retry-After")
    try:
        return float(header) if header else 1.0
    except ValueError:
        return 1.0


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
