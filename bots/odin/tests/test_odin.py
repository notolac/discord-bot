from discord_core.interactions import Interaction
from odin.commands import COMMANDS
from odin.handlers import router
from odin.services.report_log import ReportLog


def test_every_declared_command_has_a_handler():
    assert {c.name for c in COMMANDS} == set(router.command_names)


def test_command_payloads():
    payloads = {c.name: c.to_payload() for c in COMMANDS}
    assert payloads["timeout"]["options"][1]["max_value"] == 40320
    assert payloads["purge"]["default_member_permissions"] == str(1 << 13)
    assert (
        payloads["Report message"]["type"] == 3 and payloads["Report message"]["description"] == ""
    )
    assert payloads["View history"]["type"] == 2
    assert payloads["View history"]["name_localizations"] == {"es-ES": "Ver historial"}


async def test_warn_records_and_notifies(ctx, fake_discord, settings, command):
    interaction = Interaction.model_validate(
        command(
            "warn",
            [
                {"name": "user", "type": 6, "value": "u1"},
                {"name": "reason", "type": 3, "value": "spam"},
            ],
        )
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64 and "spam" in result.response["data"]["content"]
    assert fake_discord.calls[0][:2] == ("POST", "/api/v10/channels/9999/messages")
    records = ReportLog(settings.odin_reports_dir).for_target("3003", "u1")
    assert len(records) == 1 and records[0].action == "warn" and records[0].moderator_id == "5005"


async def test_timeout_patches_member(ctx, fake_discord, settings, command):
    interaction = Interaction.model_validate(
        command(
            "timeout",
            [
                {"name": "user", "type": 6, "value": "u1"},
                {"name": "minutes", "type": 4, "value": 30},
            ],
        )
    )
    result = await router.dispatch(interaction, ctx)
    assert result.response["data"]["flags"] == 64
    method, path, body = fake_discord.calls[0]
    assert (method, path) == ("PATCH", "/api/v10/guilds/3003/members/u1")
    assert "communication_disabled_until" in body
    assert ReportLog(settings.odin_reports_dir).for_target("3003", "u1")[0].extra["minutes"] == 30


async def test_timeout_failure_is_reported(ctx, fake_discord, command):
    fake_discord.fail_paths["/members/u1"] = 403
    interaction = Interaction.model_validate(
        command(
            "timeout",
            [
                {"name": "user", "type": 6, "value": "u1"},
                {"name": "minutes", "type": 4, "value": 5},
            ],
        )
    )
    result = await router.dispatch(interaction, ctx)
    assert "Missing Permissions" in result.response["data"]["content"]


async def test_purge_asks_for_confirmation(ctx, command):
    interaction = Interaction.model_validate(
        command("purge", [{"name": "count", "type": 4, "value": 7}])
    )
    result = await router.dispatch(interaction, ctx)
    buttons = result.response["data"]["components"][0]["components"]
    assert buttons[0]["custom_id"] == "purge_confirm_7" and buttons[0]["style"] == 4
    assert buttons[1]["custom_id"] == "purge_cancel"
    assert result.response["data"]["flags"] == 64


async def test_purge_cancel_clears_buttons(ctx, component):
    result = await router.dispatch(Interaction.model_validate(component("purge_cancel")), ctx)
    assert result.response["type"] == 7 and result.response["data"]["components"] == []


async def test_purge_confirm_is_deferred_and_bulk_deletes(ctx, fake_discord, settings, component):
    fake_discord.messages = [
        {"id": "m1", "timestamp": "2099-01-01T00:00:00+00:00"},
        {"id": "m2", "timestamp": "2099-01-01T00:00:00+00:00"},
        {"id": "m3", "timestamp": "2000-01-01T00:00:00+00:00"},  # too old for bulk delete
    ]
    result = await router.dispatch(Interaction.model_validate(component("purge_confirm_3")), ctx)
    assert result.response == {"type": 6}
    await result.background
    paths = [(m, p) for m, p, _ in fake_discord.calls]
    assert paths == [
        ("GET", "/api/v10/channels/4004/messages"),
        ("POST", "/api/v10/channels/4004/messages/bulk-delete"),
        ("PATCH", "/api/v10/webhooks/2002/tok/messages/@original"),
    ]
    assert fake_discord.calls[1][2] == {"messages": ["m1", "m2"]}
    assert "2" in fake_discord.calls[2][2]["content"]
    assert fake_discord.calls[2][2]["components"] == []
    log = ReportLog(settings.odin_reports_dir)
    assert log.path_for("3003").read_text().count('"action":"purge"') == 1


async def test_report_message_forwards_to_mod_channel(ctx, fake_discord, settings, command):
    payload = command(
        "Report message",
        target_id="m42",
        resolved={
            "messages": {
                "m42": {
                    "id": "m42",
                    "channel_id": "4004",
                    "content": "bad words",
                    "author": {"id": "u9", "username": "x"},
                }
            }
        },
    )
    payload["data"]["type"] = 3
    result = await router.dispatch(Interaction.model_validate(payload), ctx)
    assert result.response["data"]["flags"] == 64
    method, path, body = fake_discord.calls[0]
    assert (method, path) == ("POST", "/api/v10/channels/9999/messages")
    assert "bad words" in body["content"] and "/channels/3003/4004/m42" in body["content"]
    assert ReportLog(settings.odin_reports_dir).for_target("3003", "u9")[0].action == "report"


async def test_report_without_mod_channel_is_refused(ctx, settings, fake_discord, command):
    settings.odin_mod_channel_id = None
    payload = command("Report message", target_id="m42")
    result = await router.dispatch(Interaction.model_validate(payload), ctx)
    assert "not configured" in result.response["data"]["content"]
    assert fake_discord.calls == []


async def test_view_history_lists_records(ctx, settings, command):
    warn = command(
        "warn",
        [
            {"name": "user", "type": 6, "value": "u1"},
            {"name": "reason", "type": 3, "value": "spam"},
        ],
    )
    await router.dispatch(Interaction.model_validate(warn), ctx)
    payload = command("View history", target_id="u1")
    payload["data"]["type"] = 2
    result = await router.dispatch(Interaction.model_validate(payload), ctx)
    content = result.response["data"]["content"]
    assert "<@u1>" in content and "**warn**" in content and "spam" in content

    empty = command("View history", target_id="nobody")
    result = await router.dispatch(Interaction.model_validate(empty), ctx)
    assert "No moderation records" in result.response["data"]["content"]
