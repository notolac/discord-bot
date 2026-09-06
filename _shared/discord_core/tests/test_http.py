import httpx
import pytest

from discord_core.http import DiscordAPIError, DiscordClient


async def test_headers_include_bot_auth_and_user_agent():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    async with DiscordClient("abc", transport=httpx.MockTransport(handler)) as client:
        await client.request("GET", "/users/@me")
    assert seen["authorization"] == "Bot abc"
    assert seen["user-agent"].startswith("DiscordBot (https://")


async def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("discord_core.http.asyncio.sleep", fake_sleep)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, json={"retry_after": 0.25, "global": False})
        return httpx.Response(200, json={"done": True})

    async with DiscordClient("t", transport=httpx.MockTransport(handler)) as client:
        result = await client.request("GET", "/x")
    assert result == {"done": True}
    assert sleeps == [0.25]


async def test_error_body_is_surfaced():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "code": 50035,
                "message": "Invalid Form Body",
                "errors": {"name": {"_errors": []}},
            },
        )

    async with DiscordClient("t", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DiscordAPIError) as excinfo:
            await client.put_global_commands("app", [])
    assert excinfo.value.status == 400
    assert excinfo.value.code == 50035
    assert "Invalid Form Body" in str(excinfo.value)


async def test_204_returns_none_and_audit_reason_header():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(204)

    async with DiscordClient("t", transport=httpx.MockTransport(handler)) as client:
        result = await client.add_member_role("g", "u", "r", reason="onboarding")
    assert result is None
    assert seen["x-audit-log-reason"] == "onboarding"


async def test_bulk_delete_single_id_uses_delete_endpoint():
    paths: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append((request.method, request.url.path))
        return httpx.Response(204)

    async with DiscordClient("t", transport=httpx.MockTransport(handler)) as client:
        await client.bulk_delete_messages("c", ["m1"])
        await client.bulk_delete_messages("c", ["m1", "m2"])
    assert paths == [
        ("DELETE", "/api/v10/channels/c/messages/m1"),
        ("POST", "/api/v10/channels/c/messages/bulk-delete"),
    ]
