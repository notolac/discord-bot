import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from discord_core import DiscordClient, InteractionContext
from discord_core.i18n import Localizer
from odin import BOT_ROOT
from odin.settings import Settings


class FakeDiscord:
    """Records calls; returns canned channel messages for GET and 200/204 otherwise."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.fail_paths: dict[str, int] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        for fragment, status in self.fail_paths.items():
            if fragment in request.url.path:
                return httpx.Response(
                    status, json={"code": 50013, "message": "Missing Permissions"}
                )
        if request.method == "GET" and request.url.path.endswith("/messages"):
            return httpx.Response(200, json=self.messages)
        if request.method in ("PUT", "DELETE") or request.url.path.endswith("bulk-delete"):
            return httpx.Response(204)
        return httpx.Response(200, json={"id": "m1"})


@pytest.fixture
def fake_discord() -> FakeDiscord:
    return FakeDiscord()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        discord_app_id="2002",
        discord_public_key="00",
        discord_bot_token="t",  # type: ignore[arg-type]
        odin_mod_channel_id="9999",
        odin_reports_dir=tmp_path / "reports",
        _env_file=None,  # type: ignore[call-arg]
    )


@pytest.fixture
def ctx(settings: Settings, fake_discord: FakeDiscord) -> InteractionContext:
    client = DiscordClient("t", transport=httpx.MockTransport(fake_discord))
    return InteractionContext(
        settings=settings, client=client, i18n=Localizer.from_dir(BOT_ROOT / "i18n")
    )


def _base(type_: int, *, user_id: str = "5005") -> dict[str, Any]:
    return {
        "id": "1001",
        "application_id": "2002",
        "type": type_,
        "token": "tok",
        "version": 1,
        "guild_id": "3003",
        "channel_id": "4004",
        "locale": "en-US",
        "member": {"user": {"id": user_id, "username": "mod"}, "roles": []},
    }


def _command(name: str, options: list[dict[str, Any]] | None = None, **data: Any) -> dict[str, Any]:
    payload = _base(2)
    payload["data"] = {"id": "6006", "name": name, "type": 1, "options": options or [], **data}
    return payload


def _component(custom_id: str) -> dict[str, Any]:
    payload = _base(3)
    payload["message"] = {"id": "7007"}
    payload["data"] = {"custom_id": custom_id, "component_type": 2}
    return payload


@pytest.fixture
def command():
    return _command


@pytest.fixture
def component():
    return _component
