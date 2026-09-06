from discord_core.interactions import Interaction
from heimdal.commands import COMMANDS
from heimdal.handlers import router


def test_every_declared_command_has_a_handler():
    assert {c.name for c in COMMANDS} == set(router.command_names)


def test_command_payloads_serialize_with_localizations():
    payloads = {c.name: c.to_payload() for c in COMMANDS}
    assert payloads["welcome"]["name_localizations"] == {"es-ES": "bienvenida"}
    assert payloads["welcome"]["default_member_permissions"] == str(1 << 5)
    assert payloads["introduce"]["name_localizations"] == {"es-ES": "presentarme"}


async def test_welcome_targets_option_user(ctx, command):
    interaction = Interaction.model_validate(
        command("welcome", [{"name": "user", "type": 6, "value": "9009"}])
    )
    result = await router.dispatch(interaction, ctx)
    data = result.response["data"]
    assert data["flags"] & (1 << 15)
    assert data["allowed_mentions"] == {"users": ["9009"]}
    row = data["components"][0]["components"][-1]
    assert row["components"][0]["custom_id"] == "rules_accept_9009"
    assert row["components"][1]["url"] == "https://example.com/rules"


async def test_rules_accept_rejects_other_users(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("rules_accept_9009", user_id="5005"))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4 and result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def test_rules_accept_grants_role_and_updates_card(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("rules_accept_9009", user_id="9009"))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 7
    assert fake_discord.calls == [("PUT", "/api/v10/guilds/3003/members/9009/roles/777", None)]


async def test_rules_accept_reports_permission_error(ctx, fake_discord, component):
    fake_discord.fail_paths["/roles/777"] = 403
    interaction = Interaction.model_validate(component("rules_accept_9009", user_id="9009"))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4 and result.response["data"]["flags"] == 64


async def test_roles_shows_configured_options_with_defaults(ctx, command):
    result = await router.dispatch(Interaction.model_validate(command("roles")), ctx)
    select = result.response["data"]["components"][0]["components"][0]
    assert select["custom_id"] == "roles_pick"
    assert [o["value"] for o in select["options"]] == ["111", "222"]
    assert select["options"][0]["default"] is True
    assert select["max_values"] == 2


async def test_roles_pick_only_grants_known_roles(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("roles_pick", ["222", "999"]))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 7
    assert "Dev" in result.response["data"]["content"]
    assert result.response["data"]["components"] == []
    assert [c[1] for c in fake_discord.calls] == ["/api/v10/guilds/3003/members/5005/roles/222"]


async def test_introduce_opens_modal(ctx, command):
    result = await router.dispatch(Interaction.model_validate(command("introduce")), ctx)
    assert result.response["type"] == 9
    assert result.response["data"]["custom_id"] == "introduce_modal"
    assert len(result.response["data"]["components"]) == 3


async def test_introduce_submit_posts_card_in_channel(ctx, fake_discord, modal):
    interaction = Interaction.model_validate(
        modal(
            "introduce_modal",
            {"intro_name": "Neo", "intro_about": "I know kung fu", "intro_interests": "matrix"},
        )
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4
    texts = [c["content"] for c in result.response["data"]["components"][0]["components"]]
    assert any("Neo" in t for t in texts) and any("matrix" in t for t in texts)
    assert fake_discord.calls == []


async def test_introduce_submit_posts_to_configured_channel(ctx, fake_discord, settings, modal):
    settings.heimdal_intro_channel_id = "8888"
    interaction = Interaction.model_validate(
        modal("introduce_modal", {"intro_name": "Neo", "intro_about": "hi"})
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls[0][:2] == ("POST", "/api/v10/channels/8888/messages")
