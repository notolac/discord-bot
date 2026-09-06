from discord_core.interactions import Interaction, Permissions
from heimdal.commands import COMMANDS
from heimdal.handlers import router
from heimdal.roles import (
    ROLE_ASK_ID,
    ApprovalKey,
    approval_button_id,
    parse_approval_button,
    parse_role_request_value,
)


def test_every_declared_command_has_a_handler():
    assert {c.name for c in COMMANDS} == set(router.command_names)


def test_command_payloads_serialize_with_localizations():
    payloads = {c.name: c.to_payload() for c in COMMANDS}
    assert payloads["welcome"]["name_localizations"] == {"es-ES": "bienvenida"}
    assert payloads["welcome"]["default_member_permissions"] == str(1 << 5)
    assert payloads["introduce"]["name_localizations"] == {"es-ES": "presentarme"}
    request = payloads["request-role"]
    assert request["name_localizations"] == {"es-ES": "solicitar-rol"}
    assert "default_member_permissions" not in request
    choices = {c["value"] for c in request["options"][0]["choices"]}
    assert choices == {"organizer", "speaker", "startups", "enterprises"}


async def test_welcome_without_user_posts_public_card(ctx, command):
    result = await router.dispatch(Interaction.model_validate(command("welcome")), ctx)
    data = result.response["data"]
    assert data["flags"] & (1 << 15)
    assert data["allowed_mentions"]["parse"] == []
    custom_ids = _all_custom_ids(data["components"])
    assert "rules_accept" in custom_ids
    assert not any(cid.startswith("rules_accept_") for cid in custom_ids)
    assert ROLE_ASK_ID in custom_ids
    select = _first_select(data["components"])
    assert select is not None
    assert {o["value"] for o in select["options"]} == {"org", "spk", "stu", "ent"}
    assert "800" not in {o["value"] for o in select["options"]}


async def test_welcome_targets_option_user(ctx, command):
    interaction = Interaction.model_validate(
        command("welcome", [{"name": "user", "type": 6, "value": "9009"}])
    )
    result = await router.dispatch(interaction, ctx)
    data = result.response["data"]
    assert data["flags"] & (1 << 15)
    assert data["allowed_mentions"]["users"] == ["9009"]
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
    assert fake_discord.audit_reasons == ["Heimdal: rules accepted"]


async def test_rules_accept_public_grants_only_member_to_clicker(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component("rules_accept", ["800", "900"], user_id="5005")
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4 and result.response["data"]["flags"] == 64
    assert fake_discord.calls == [("PUT", "/api/v10/guilds/3003/members/5005/roles/777", None)]
    assert fake_discord.audit_reasons == ["Heimdal: rules accepted"]


async def test_rules_accept_public_is_idempotent_when_already_member(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component("rules_accept", user_id="5005", roles=["777"])
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def test_rules_accept_skips_put_without_guild(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("rules_accept", guild_id=None))
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def test_rules_accept_reports_permission_error(ctx, fake_discord, component):
    fake_discord.fail_paths["/roles/777"] = 403
    interaction = Interaction.model_validate(component("rules_accept_9009", user_id="9009"))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4 and result.response["data"]["flags"] == 64
    assert result.response["data"].get("components") is None


async def test_roles_shows_configured_options_with_defaults(ctx, command):
    result = await router.dispatch(Interaction.model_validate(command("roles")), ctx)
    select = result.response["data"]["components"][0]["components"][0]
    assert select["custom_id"] == "roles_pick"
    assert [o["value"] for o in select["options"]] == ["111", "222"]
    assert select["options"][0]["default"] is True
    assert select["max_values"] == 2


async def test_roles_excludes_approval_and_denied_ids(ctx, settings, command):
    settings.heimdal_interest_roles = "Academia:333,Startups:802,admin:900,Gaming:111"
    result = await router.dispatch(Interaction.model_validate(command("roles")), ctx)
    select = result.response["data"]["components"][0]["components"][0]
    assert [o["value"] for o in select["options"]] == ["333", "111"]


async def test_roles_pick_only_grants_known_roles(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("roles_pick", ["222", "999"]))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 7
    assert "Dev" in result.response["data"]["content"]
    assert result.response["data"]["components"] == []
    assert [c[1] for c in fake_discord.calls] == ["/api/v10/guilds/3003/members/5005/roles/222"]


async def test_roles_pick_ignores_startups_enterprises_and_staff_ids(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component("roles_pick", ["802", "803", "900", "901", "800", "777"])
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 7
    assert fake_discord.calls == []


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


async def test_request_role_opens_modal_for_known_choice(ctx, command):
    interaction = Interaction.model_validate(
        command("request-role", [{"name": "role", "type": 3, "value": "organizer"}])
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 9
    assert result.response["data"]["custom_id"] == "role_req_org"
    assert len(result.response["data"]["title"]) <= 45


async def test_request_role_rejects_unknown_choice(ctx, fake_discord, command):
    interaction = Interaction.model_validate(
        command("request-role", [{"name": "role", "type": 3, "value": "admin"}])
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def test_role_ask_forged_select_value_does_not_open_modal(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component(ROLE_ASK_ID, ["800", "900"]))
    result = await router.dispatch(interaction, ctx)
    assert result.response["type"] == 4 and result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def test_role_request_submit_posts_staff_card_without_role_snowflakes(
    ctx, fake_discord, modal
):
    interaction = Interaction.model_validate(
        modal("role_req_org", {"req_aff": "BAD meetup", "req_note": "https://example.com"})
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls[0][:2] == ("POST", "/api/v10/channels/5555/messages")
    body = fake_discord.calls[0][2]
    assert body["allowed_mentions"] == {"parse": [], "users": ["5005"]}
    ids = _all_custom_ids(body["components"])
    assert "role_ok_org_5005" in ids and "role_no_org_5005" in ids
    assert all("800" not in cid for cid in ids)
    assert "@everyone" not in str(body["components"])


async def test_role_request_submit_forged_key_does_not_post(ctx, fake_discord, modal):
    interaction = Interaction.model_validate(
        modal("role_req_adm", {"req_aff": "x", "req_note": "y"})
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    assert fake_discord.calls == []


async def _run(interaction: Interaction, ctx):
    result = await router.dispatch(interaction, ctx)
    if result.background is not None:
        await result.background
    return result


def _puts(fake_discord) -> list:
    return [c for c in fake_discord.calls if c[0] == "PUT"]


def _channel_message_patches(fake_discord) -> list:
    return [
        c
        for c in fake_discord.calls
        if c[0] == "PATCH" and "/channels/" in c[1] and "/messages/" in c[1]
    ]


async def test_approval_approve_by_non_staff_does_not_put(ctx, fake_discord, component):
    interaction = Interaction.model_validate(component("role_ok_org_5005", user_id="5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == []


async def test_approval_approve_by_requester_does_not_put(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component("role_ok_org_5005", user_id="5005", roles=["111"])
    )
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == []


async def test_approval_approve_missing_member_does_not_put(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component("role_ok_org_5005", user_id="6006", with_member=False)
    )
    result = await _run(interaction, ctx)
    assert _puts(fake_discord) == []
    assert result.response["type"] == 5


async def test_approval_approve_forged_key_does_not_put(ctx, fake_discord, staff_component):
    interaction = Interaction.model_validate(staff_component("role_ok_adm_5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == []


async def test_approval_approve_unknown_key_does_not_put(ctx, fake_discord, staff_component):
    interaction = Interaction.model_validate(staff_component("role_ok_zzz_5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == []


async def test_approval_approve_by_staff_puts_mapped_role_on_requester(
    ctx, fake_discord, staff_component
):
    interaction = Interaction.model_validate(staff_component("role_ok_org_5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == [("PUT", "/api/v10/guilds/3003/members/5005/roles/800", None)]
    assert "Heimdal: approved organizer by 6006" in fake_discord.audit_reasons
    patches = _channel_message_patches(fake_discord)
    assert patches and patches[0][1] == "/api/v10/channels/4004/messages/7007"
    body = patches[0][2]
    assert body["allowed_mentions"]["parse"] == []
    assert not _all_custom_ids(body["components"])


async def test_approval_self_approve_mentions_requester_once(ctx, fake_discord, staff_component):
    interaction = Interaction.model_validate(staff_component("role_ok_org_6006"))
    await _run(interaction, ctx)
    assert _puts(fake_discord) == [("PUT", "/api/v10/guilds/3003/members/6006/roles/800", None)]
    users = _channel_message_patches(fake_discord)[0][2]["allowed_mentions"]["users"]
    assert users == ["6006"]


async def test_approval_approve_by_manage_guild_permission(ctx, fake_discord, component):
    interaction = Interaction.model_validate(
        component(
            "role_ok_spk_5005",
            user_id="6006",
            roles=[],
            permissions=str(int(Permissions.MANAGE_GUILD)),
        )
    )
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == [("PUT", "/api/v10/guilds/3003/members/5005/roles/801", None)]


async def test_approval_approve_403_does_not_update_card_as_success(
    ctx, fake_discord, staff_component
):
    fake_discord.fail_paths["/roles/800"] = 403
    interaction = Interaction.model_validate(staff_component("role_ok_org_5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _channel_message_patches(fake_discord) == []


async def test_approval_deny_does_not_put(ctx, fake_discord, staff_component):
    interaction = Interaction.model_validate(staff_component("role_no_org_5005"))
    result = await _run(interaction, ctx)
    assert result.response["type"] == 5
    assert _puts(fake_discord) == []
    patches = _channel_message_patches(fake_discord)
    assert patches and not _all_custom_ids(patches[0][2]["components"])


def test_parse_approval_button_rejects_role_snowflakes_in_key_slot():
    assert parse_approval_button("role_ok_800_5005") is None
    assert parse_approval_button("role_ok_org_5005") == (True, ApprovalKey.ORGANIZER, "5005")
    assert parse_role_request_value("800") is None
    assert approval_button_id(True, ApprovalKey.ORGANIZER, "5005") == "role_ok_org_5005"


def _all_custom_ids(components: list) -> list[str]:
    found: list[str] = []
    for item in components:
        if "custom_id" in item:
            found.append(item["custom_id"])
        nested = item.get("components")
        if nested:
            found.extend(_all_custom_ids(nested))
    return found


def _first_select(components: list) -> dict | None:
    for item in components:
        if item.get("type") == 3:
            return item
        nested = item.get("components")
        if nested:
            found = _first_select(nested)
            if found:
                return found
    return None
