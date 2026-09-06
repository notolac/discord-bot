import pytest

from discord_core import responses
from discord_core.interactions import ButtonStyle, MessageFlags


def test_pong_shape():
    assert responses.pong() == {"type": 1}


def test_message_defaults_to_no_mentions():
    payload = responses.message("hi")
    assert payload["type"] == 4
    assert payload["data"]["content"] == "hi"
    assert payload["data"]["allowed_mentions"] == {"parse": []}
    assert "flags" not in payload["data"]


def test_ephemeral_sets_flag_64():
    payload = responses.ephemeral("secret")
    assert payload["data"]["flags"] == 64


def test_components_v2_sets_flag_and_forbids_content():
    payload = responses.message(components=[responses.text_display("x")], components_v2=True)
    assert payload["data"]["flags"] & MessageFlags.IS_COMPONENTS_V2
    with pytest.raises(ValueError):
        responses.message("content", components_v2=True)


def test_deferred_only_carries_ephemeral_flag():
    assert responses.deferred() == {"type": 5}
    assert responses.deferred(ephemeral=True) == {"type": 5, "data": {"flags": 64}}
    assert responses.deferred_update() == {"type": 6}


def test_update_message_type_7():
    assert responses.update_message("edited")["type"] == 7


def test_modal_validation():
    field = responses.label("Name", responses.text_input("name"))
    payload = responses.modal("m1", "Title", [field])
    assert payload["type"] == 9
    assert payload["data"]["custom_id"] == "m1"
    with pytest.raises(ValueError):
        responses.modal("m1", "Title", [])
    with pytest.raises(ValueError):
        responses.modal("m1", "x" * 46, [field])


def test_autocomplete_limit():
    assert responses.autocomplete([responses.choice("a", "a")])["type"] == 8
    with pytest.raises(ValueError):
        responses.autocomplete([responses.choice(str(i), i) for i in range(26)])


def test_button_rules():
    assert responses.button("Go", custom_id="go")["custom_id"] == "go"
    link = responses.button("Docs", style=ButtonStyle.LINK, url="https://example.com")
    assert link["url"] == "https://example.com" and "custom_id" not in link
    with pytest.raises(ValueError):
        responses.button("x")
    with pytest.raises(ValueError):
        responses.button("x", style=ButtonStyle.LINK)


def test_string_select_bounds():
    opts = [responses.select_option("A", "a")]
    assert responses.string_select("s", opts)["type"] == 3
    with pytest.raises(ValueError):
        responses.string_select("s", [])
