import httpx
import pytest

from discord_core.commands import (
    Choice,
    Command,
    GlobalOverwriteRefusedError,
    Option,
    diff_commands,
    sync_commands,
)
from discord_core.http import DiscordClient
from discord_core.interactions import CommandType, OptionType, Permissions


def test_chat_input_payload_orders_required_first_and_serializes_permissions():
    cmd = Command(
        name="timeout",
        description="Time a member out",
        options=[
            Option("reason", "Why", required=False),
            Option("user", "Who", type=OptionType.USER, required=True),
            Option("minutes", "How long", type=OptionType.INTEGER, min_value=1, max_value=40320),
        ],
        default_member_permissions=Permissions.MODERATE_MEMBERS,
        name_localizations={"es-ES": "silenciar"},
    )
    payload = cmd.to_payload()
    assert payload["type"] == 1
    assert [o["name"] for o in payload["options"]] == ["user", "reason", "minutes"]
    assert payload["options"][0]["required"] is True
    assert payload["options"][2]["min_value"] == 1
    assert payload["default_member_permissions"] == str(1 << 40)
    assert payload["integration_types"] == [0] and payload["contexts"] == [0]
    assert payload["name_localizations"] == {"es-ES": "silenciar"}


def test_user_command_requires_empty_description():
    assert Command(name="View history", type=CommandType.USER).to_payload()["description"] == ""
    with pytest.raises(ValueError):
        Command(name="Report", type=CommandType.MESSAGE, description="x").to_payload()


def test_chat_input_name_validation():
    with pytest.raises(ValueError):
        Command(name="Bad Name", description="d").to_payload()
    with pytest.raises(ValueError):
        Command(name="upper", description="d", options=[Option("BAD", "d")]).to_payload()


def test_choices_and_autocomplete_are_exclusive():
    opt = Option("kind", "d", choices=[Choice("A", "a")], autocomplete=True)
    with pytest.raises(ValueError):
        opt.to_payload()


def test_diff_detects_added_removed_changed_unchanged():
    remote = [
        {
            "id": "1",
            "type": 1,
            "name": "ping",
            "description": "Pong",
            "integration_types": [0],
            "contexts": [0],
        },
        {
            "id": "2",
            "type": 1,
            "name": "old",
            "description": "Gone",
            "integration_types": [0],
            "contexts": [0],
        },
        {
            "id": "3",
            "type": 1,
            "name": "warn",
            "description": "Old text",
            "integration_types": [0],
            "contexts": [0],
        },
    ]
    local = [
        Command("ping", "Pong"),
        Command("warn", "New text"),
        Command("new", "Brand new"),
    ]
    diff = diff_commands(remote, local)
    assert diff.added == ["new"]
    assert diff.removed == ["old"]
    assert diff.changed == ["warn"]
    assert diff.unchanged == ["ping"]
    assert not diff.is_empty


def test_diff_ignores_remote_only_metadata():
    local = [Command("ping", "Pong")]
    remote = [
        {**local[0].to_payload(), "id": "1", "application_id": "2", "version": "3", "nsfw": False}
    ]
    assert diff_commands(remote, local).is_empty


def _client_with(handler) -> DiscordClient:
    return DiscordClient("token", transport=httpx.MockTransport(handler))


async def test_sync_guild_puts_when_diff_non_empty():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[])

    async with _client_with(handler) as client:
        diff = await sync_commands(client, "app", [Command("ping", "Pong")], guild_id="g1")
    assert diff.added == ["ping"]
    assert calls == [
        ("GET", "/api/v10/applications/app/guilds/g1/commands"),
        ("PUT", "/api/v10/applications/app/guilds/g1/commands"),
    ]


async def test_sync_dry_run_never_puts():
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return httpx.Response(200, json=[])

    async with _client_with(handler) as client:
        await sync_commands(client, "app", [Command("ping", "Pong")], guild_id="g1", dry_run=True)
    assert calls == ["GET"]


async def test_global_sync_refuses_deletions_without_confirmation():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json=[Command("old", "x").to_payload() | {"id": "1"}])
        return httpx.Response(200, json=[])

    async with _client_with(handler) as client:
        with pytest.raises(GlobalOverwriteRefusedError):
            await sync_commands(client, "app", [Command("ping", "Pong")])
        diff = await sync_commands(client, "app", [Command("ping", "Pong")], confirm_deletions=True)
    assert diff.removed == ["old"]
