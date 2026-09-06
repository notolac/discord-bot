import httpx

from bot_template.commands import COMMANDS
from bot_template.handlers import router
from discord_core import DiscordClient, DiscordSettings, InteractionContext
from discord_core.i18n import Localizer
from discord_core.interactions import Interaction


def _ctx() -> InteractionContext:
    settings = DiscordSettings(
        discord_app_id="1",
        discord_public_key="00",
        discord_bot_token="t",  # type: ignore[arg-type]
    )
    client = DiscordClient(
        "t", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    return InteractionContext(settings=settings, client=client, i18n=Localizer())


def test_every_declared_command_has_a_handler():
    assert {c.name for c in COMMANDS} <= set(router.command_names)


async def test_ping_replies_ephemeral():
    interaction = Interaction.model_validate(
        {
            "id": "1",
            "application_id": "1",
            "type": 2,
            "token": "t",
            "version": 1,
            "user": {"id": "9", "username": "neo"},
            "data": {"id": "1", "name": "ping", "type": 1},
        }
    )
    result = await router.dispatch(interaction, _ctx())
    assert result.response["type"] == 4
    assert result.response["data"]["flags"] == 64
