from discord_core.interactions import Interaction, InteractionType


def test_parse_command_with_member(command_interaction):
    interaction = Interaction.model_validate(
        command_interaction("warn", [{"name": "user", "type": 6, "value": "9"}])
    )
    assert interaction.type == InteractionType.APPLICATION_COMMAND
    assert interaction.command_name == "warn"
    assert interaction.invoking_user.id == "5005"
    assert interaction.option("user") == "9"
    assert interaction.subcommand_path() == []


def test_subcommand_path_and_leaf_options(command_interaction):
    options = [
        {
            "name": "rule",
            "type": 2,
            "options": [
                {
                    "name": "add",
                    "type": 1,
                    "options": [{"name": "keyword", "type": 3, "value": "spam"}],
                }
            ],
        }
    ]
    interaction = Interaction.model_validate(command_interaction("automod", options))
    assert interaction.subcommand_path() == ["rule", "add"]
    assert interaction.leaf_options() == {"keyword": "spam"}


def test_dm_uses_user_field(command_interaction):
    payload = command_interaction("ping")
    payload.pop("member")
    payload["user"] = {"id": "77", "username": "dm"}
    assert Interaction.model_validate(payload).invoking_user.id == "77"


def test_unknown_fields_are_tolerated(command_interaction):
    payload = command_interaction("ping", brand_new_field={"x": 1})
    assert Interaction.model_validate(payload).command_name == "ping"


def test_modal_values_flatten_labels():
    payload = {
        "id": "1",
        "application_id": "2",
        "type": 5,
        "token": "t",
        "version": 1,
        "user": {"id": "3", "username": "u"},
        "data": {
            "custom_id": "introduce_modal",
            "components": [
                {"type": 18, "component": {"type": 4, "custom_id": "about", "value": "hello"}},
                {"type": 18, "component": {"type": 3, "custom_id": "tags", "values": ["a", "b"]}},
            ],
        },
    }
    interaction = Interaction.model_validate(payload)
    assert interaction.modal_values() == {"about": "hello", "tags": ["a", "b"]}


def test_focused_option(command_interaction):
    interaction = Interaction.model_validate(
        command_interaction("search", [{"name": "q", "type": 3, "value": "he", "focused": True}])
    )
    focused = interaction.focused_option()
    assert focused is not None and focused.value == "he"
