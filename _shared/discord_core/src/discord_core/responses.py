"""Builders for interaction responses and message/modal components.

All builders return plain ``dict`` payloads ready to be JSON-encoded. Shapes follow:
https://docs.discord.com/developers/interactions/receiving-and-responding#interaction-response-object
https://docs.discord.com/developers/components/reference
"""

from __future__ import annotations

from typing import Any

from discord_core.interactions import (
    ButtonStyle,
    CallbackType,
    ComponentType,
    MessageFlags,
    TextInputStyle,
)

NO_MENTIONS: dict[str, Any] = {"parse": []}

# ------------------------------------------------------------------ responses


def pong() -> dict[str, Any]:
    """ACK a ``PING`` (type 1)."""
    return {"type": CallbackType.PONG}


def _message_data(
    content: str | None,
    *,
    components: list[dict[str, Any]] | None,
    embeds: list[dict[str, Any]] | None,
    flags: int,
    allowed_mentions: dict[str, Any] | None,
    components_v2: bool,
) -> dict[str, Any]:
    if components_v2:
        flags |= MessageFlags.IS_COMPONENTS_V2
        if content is not None:
            msg = "Components v2 messages cannot set `content`; use text_display() instead"
            raise ValueError(msg)
    data: dict[str, Any] = {"allowed_mentions": allowed_mentions or NO_MENTIONS}
    if content is not None:
        data["content"] = content
    if components is not None:
        # An explicit empty list removes existing components on UPDATE_MESSAGE / edits.
        data["components"] = components
    if embeds:
        data["embeds"] = embeds
    if flags:
        data["flags"] = int(flags)
    return data


def message(
    content: str | None = None,
    *,
    components: list[dict[str, Any]] | None = None,
    embeds: list[dict[str, Any]] | None = None,
    ephemeral: bool = False,
    flags: int = 0,
    allowed_mentions: dict[str, Any] | None = None,
    components_v2: bool = False,
) -> dict[str, Any]:
    """Respond with a new message (callback type 4).

    ``allowed_mentions`` defaults to *no pings* — pass explicitly to mention someone.
    """
    if ephemeral:
        flags |= MessageFlags.EPHEMERAL
    return {
        "type": CallbackType.CHANNEL_MESSAGE_WITH_SOURCE,
        "data": _message_data(
            content,
            components=components,
            embeds=embeds,
            flags=flags,
            allowed_mentions=allowed_mentions,
            components_v2=components_v2,
        ),
    }


def ephemeral(content: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Shortcut for ``message(..., ephemeral=True)``."""
    return message(content, ephemeral=True, **kwargs)


def deferred(*, ephemeral: bool = False) -> dict[str, Any]:
    """ACK now, edit later (callback type 5). Only ``EPHEMERAL`` is a valid flag here."""
    payload: dict[str, Any] = {"type": CallbackType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE}
    if ephemeral:
        payload["data"] = {"flags": int(MessageFlags.EPHEMERAL)}
    return payload


def deferred_update() -> dict[str, Any]:
    """Components only: ACK without loading state, edit the original message later (type 6)."""
    return {"type": CallbackType.DEFERRED_UPDATE_MESSAGE}


def update_message(
    content: str | None = None,
    *,
    components: list[dict[str, Any]] | None = None,
    embeds: list[dict[str, Any]] | None = None,
    flags: int = 0,
    allowed_mentions: dict[str, Any] | None = None,
    components_v2: bool = False,
) -> dict[str, Any]:
    """Components only: edit the message the component belongs to (callback type 7)."""
    return {
        "type": CallbackType.UPDATE_MESSAGE,
        "data": _message_data(
            content,
            components=components,
            embeds=embeds,
            flags=flags,
            allowed_mentions=allowed_mentions,
            components_v2=components_v2,
        ),
    }


def autocomplete(choices: list[dict[str, Any]]) -> dict[str, Any]:
    """Autocomplete result (callback type 8), max 25 choices."""
    if len(choices) > 25:
        msg = "autocomplete supports at most 25 choices"
        raise ValueError(msg)
    return {
        "type": CallbackType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT,
        "data": {"choices": choices},
    }


def modal(custom_id: str, title: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    """Open a modal (callback type 9). 1–5 components, title ≤ 45 chars."""
    if not 1 <= len(components) <= 5:
        msg = "a modal needs between 1 and 5 components"
        raise ValueError(msg)
    if len(title) > 45:
        msg = "modal title must be at most 45 characters"
        raise ValueError(msg)
    return {
        "type": CallbackType.MODAL,
        "data": {"custom_id": custom_id, "title": title, "components": components},
    }


def choice(name: str, value: str | float) -> dict[str, Any]:
    """Autocomplete / command option choice."""
    return {"name": name, "value": value}


# ----------------------------------------------------------------- components


def action_row(*components: dict[str, Any]) -> dict[str, Any]:
    """Action row container (max 5 buttons or 1 select)."""
    return {"type": ComponentType.ACTION_ROW, "components": list(components)}


def button(
    label: str,
    *,
    custom_id: str | None = None,
    style: ButtonStyle = ButtonStyle.PRIMARY,
    url: str | None = None,
    emoji: dict[str, Any] | None = None,
    disabled: bool = False,
) -> dict[str, Any]:
    """Button. Link buttons take ``url`` and no ``custom_id``; the rest need ``custom_id``."""
    payload: dict[str, Any] = {"type": ComponentType.BUTTON, "style": int(style), "label": label}
    if style == ButtonStyle.LINK:
        if not url:
            msg = "link buttons require `url`"
            raise ValueError(msg)
        payload["url"] = url
    else:
        if not custom_id:
            msg = "non-link buttons require `custom_id`"
            raise ValueError(msg)
        payload["custom_id"] = custom_id
    if emoji:
        payload["emoji"] = emoji
    if disabled:
        payload["disabled"] = True
    return payload


def select_option(
    label: str,
    value: str,
    *,
    description: str | None = None,
    emoji: dict[str, Any] | None = None,
    default: bool = False,
) -> dict[str, Any]:
    """Option for ``string_select``."""
    option: dict[str, Any] = {"label": label, "value": value}
    if description:
        option["description"] = description
    if emoji:
        option["emoji"] = emoji
    if default:
        option["default"] = True
    return option


def string_select(
    custom_id: str,
    options: list[dict[str, Any]],
    *,
    placeholder: str | None = None,
    min_values: int = 1,
    max_values: int = 1,
    disabled: bool = False,
) -> dict[str, Any]:
    """String select menu (1–25 options)."""
    if not 1 <= len(options) <= 25:
        msg = "string_select needs between 1 and 25 options"
        raise ValueError(msg)
    payload: dict[str, Any] = {
        "type": ComponentType.STRING_SELECT,
        "custom_id": custom_id,
        "options": options,
        "min_values": min_values,
        "max_values": max_values,
    }
    if placeholder:
        payload["placeholder"] = placeholder
    if disabled:
        payload["disabled"] = True
    return payload


def text_input(
    custom_id: str,
    *,
    style: TextInputStyle = TextInputStyle.SHORT,
    placeholder: str | None = None,
    value: str | None = None,
    required: bool = True,
    min_length: int | None = None,
    max_length: int | None = None,
) -> dict[str, Any]:
    """Text input for modals (wrap it with ``label``)."""
    payload: dict[str, Any] = {
        "type": ComponentType.TEXT_INPUT,
        "custom_id": custom_id,
        "style": int(style),
        "required": required,
    }
    if placeholder:
        payload["placeholder"] = placeholder
    if value is not None:
        payload["value"] = value
    if min_length is not None:
        payload["min_length"] = min_length
    if max_length is not None:
        payload["max_length"] = max_length
    return payload


def label(
    text: str, component: dict[str, Any], *, description: str | None = None
) -> dict[str, Any]:
    """Label wrapper for modal components (Components v2 replacement of action rows)."""
    payload: dict[str, Any] = {"type": ComponentType.LABEL, "label": text, "component": component}
    if description:
        payload["description"] = description
    return payload


def text_display(content: str) -> dict[str, Any]:
    """Components v2 text block (requires ``components_v2=True`` on the message)."""
    return {"type": ComponentType.TEXT_DISPLAY, "content": content}


def separator(*, divider: bool = True, spacing: int = 1) -> dict[str, Any]:
    """Components v2 separator."""
    return {"type": ComponentType.SEPARATOR, "divider": divider, "spacing": spacing}


def container(*components: dict[str, Any], accent_color: int | None = None) -> dict[str, Any]:
    """Components v2 container (card-like grouping)."""
    payload: dict[str, Any] = {"type": ComponentType.CONTAINER, "components": list(components)}
    if accent_color is not None:
        payload["accent_color"] = accent_color
    return payload
