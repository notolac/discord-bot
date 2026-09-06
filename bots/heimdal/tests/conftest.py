import json
from typing import Any

import httpx
import pytest

from discord_core import DiscordClient, InteractionContext
from discord_core.i18n import Localizer
from heimdal import BOT_ROOT
from heimdal.settings import Settings


class FakeDiscord:
    """Records every API call and answers 200/204 unless a status override is given."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.fail_paths: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        for fragment, status in self.fail_paths.items():
            if fragment in request.url.path:
                return httpx.Response(
                    status, json={"code": 50013, "message": "Missing Permissions"}
                )
        return httpx.Response(
            204 if request.method in ("PUT", "DELETE") else 200,
            json={} if request.method not in ("PUT", "DELETE") else None,
        )


@pytest.fixture
def fake_discord() -> FakeDiscord:
    return FakeDiscord()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        discord_app_id="2002",
        discord_public_key="00",
        discord_bot_token="t",  # type: ignore[arg-type]
        heimdal_member_role_id="777",
        heimdal_interest_roles="Gaming:111,Dev:222",
        heimdal_rules_url="https://example.com/rules",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def ctx(settings: Settings, fake_discord: FakeDiscord) -> InteractionContext:
    client = DiscordClient("t", transport=httpx.MockTransport(fake_discord))
    return InteractionContext(
        settings=settings, client=client, i18n=Localizer.from_dir(BOT_ROOT / "i18n")
    )


def _command(
    name: str, options: list[dict[str, Any]] | None = None, *, user_id: str = "5005"
) -> dict[str, Any]:
    return {
        "id": "1001",
        "application_id": "2002",
        "type": 2,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "channel_id": "4004",
        "locale": "en-US",
        "member": {"user": {"id": user_id, "username": "tester"}, "roles": ["111"]},
        "data": {"id": "6006", "name": name, "type": 1, "options": options or []},
    }


def _component(
    custom_id: str, values: list[str] | None = None, *, user_id: str = "5005"
) -> dict[str, Any]:
    return {
        "id": "1001",
        "application_id": "2002",
        "type": 3,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "channel_id": "4004",
        "member": {"user": {"id": user_id, "username": "tester"}, "roles": []},
        "message": {"id": "7007"},
        "data": {"custom_id": custom_id, "component_type": 2, "values": values or []},
    }


def _modal(custom_id: str, fields: dict[str, str], *, user_id: str = "5005") -> dict[str, Any]:
    return {
        "id": "1001",
        "application_id": "2002",
        "type": 5,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "channel_id": "4004",
        "member": {"user": {"id": user_id, "username": "tester"}, "roles": []},
        "data": {
            "custom_id": custom_id,
            "components": [
                {"type": 18, "component": {"type": 4, "custom_id": key, "value": value}}
                for key, value in fields.items()
            ],
        },
    }


@pytest.fixture
def command():
    return _command


@pytest.fixture
def component():
    return _component


@pytest.fixture
def modal():
    return _modal
