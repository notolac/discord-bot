import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from discord_core import responses
from discord_core.app import create_app
from discord_core.http import DiscordClient
from discord_core.i18n import Localizer
from discord_core.interactions import Interaction
from discord_core.router import InteractionContext, Router
from discord_core.settings import DiscordSettings


def make_settings(public_key: str) -> DiscordSettings:
    return DiscordSettings(
        discord_app_id="2002",
        discord_public_key=public_key,
        discord_bot_token="secret",  # type: ignore[arg-type]
        bot_name="test",
    )


def make_ctx(settings: DiscordSettings, transport_handler=None) -> InteractionContext:
    handler = transport_handler or (lambda request: httpx.Response(200, json={}))
    client = DiscordClient("secret", transport=httpx.MockTransport(handler))
    return InteractionContext(settings=settings, client=client, i18n=Localizer())


async def test_router_dispatches_command_and_component_prefix(
    keypair, command_interaction, component_interaction
):
    router = Router()

    @router.command("ping")
    async def ping(interaction, ctx):
        return responses.ephemeral("pong")

    @router.component("roles_")
    async def roles(interaction, ctx):
        return responses.update_message(f"picked {interaction.custom_id}")

    @router.component("roles_pick_special")
    async def special(interaction, ctx):
        return responses.update_message("special")

    ctx = make_ctx(make_settings(keypair[1]))
    result = await router.dispatch(Interaction.model_validate(command_interaction("ping")), ctx)
    assert result.response["data"]["content"] == "pong"

    result = await router.dispatch(
        Interaction.model_validate(component_interaction("roles_pick_1")), ctx
    )
    assert result.response["data"]["content"] == "picked roles_pick_1"

    # longest prefix wins
    result = await router.dispatch(
        Interaction.model_validate(component_interaction("roles_pick_special_x")), ctx
    )
    assert result.response["data"]["content"] == "special"


async def test_router_unknown_returns_ephemeral(keypair, command_interaction):
    router = Router()
    ctx = make_ctx(make_settings(keypair[1]))
    result = await router.dispatch(Interaction.model_validate(command_interaction("nope")), ctx)
    assert result.response["type"] == 4
    assert result.response["data"]["flags"] == 64
    assert result.background is None


async def test_router_deferred_runs_handler_and_edits_original(keypair, command_interaction):
    router = Router()
    edits: list[dict] = []

    def transport(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH" and request.url.path.endswith("/messages/@original"):
            edits.append(json.loads(request.content))
        return httpx.Response(200, json={})

    @router.command("purge", defer=True, ephemeral=True)
    async def purge(interaction, ctx):
        return responses.message("deleted 3")

    ctx = make_ctx(make_settings(keypair[1]), transport)
    result = await router.dispatch(Interaction.model_validate(command_interaction("purge")), ctx)
    assert result.response == {"type": 5, "data": {"flags": 64}}
    assert result.background is not None
    await result.background
    assert edits == [{"content": "deleted 3", "allowed_mentions": {"parse": []}}]


def test_router_rejects_duplicate_command():
    router = Router()

    @router.command("x")
    async def one(i, c):
        return {}

    with pytest.raises(ValueError):

        @router.command("x")
        async def two(i, c):
            return {}


def test_app_ping_pong_and_signature_enforcement(keypair, signer):
    _, public_key = keypair
    router = Router()
    app = create_app(make_settings(public_key), router, client=DiscordClient("secret"))
    with TestClient(app) as client:
        body, headers = signer({"type": 1})
        assert client.post("/interactions", content=body, headers=headers).json() == {"type": 1}

        # Unsigned request → 401
        assert client.post("/interactions", content=body).status_code == 401

        # Signed but tampered body → 401
        headers_bad = dict(headers)
        assert (
            client.post("/interactions", content=body + b" ", headers=headers_bad).status_code
            == 401
        )

        assert client.get("/healthz").json()["status"] == "ok"


def test_app_routes_command_and_schedules_background(keypair, signer, command_interaction):
    _, public_key = keypair
    router = Router()
    ran = asyncio.Event()

    @router.command("hello")
    async def hello(interaction, ctx):
        return responses.message(f"hello {interaction.invoking_user.username}")

    @router.command("slow", defer=True)
    async def slow(interaction, ctx):
        ran.set()
        return responses.message("done")

    def transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    app = create_app(
        make_settings(public_key),
        router,
        client=DiscordClient("secret", transport=httpx.MockTransport(transport)),
    )
    with TestClient(app) as client:
        body, headers = signer(command_interaction("hello"))
        response = client.post("/interactions", content=body, headers=headers).json()
        assert response["data"]["content"] == "hello tester"

        body, headers = signer(command_interaction("slow"))
        response = client.post("/interactions", content=body, headers=headers).json()
        assert response == {"type": 5}
