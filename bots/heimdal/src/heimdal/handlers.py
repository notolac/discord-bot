"""Heimdal interaction handlers."""

from __future__ import annotations

from typing import Any

import structlog

from discord_core import DiscordAPIError, InteractionContext, Router, responses
from discord_core.interactions import ButtonStyle, Interaction, TextInputStyle
from heimdal.settings import Settings

router = Router()
log = structlog.get_logger("heimdal")

RULES_ACCEPT_PREFIX = "rules_accept_"
ROLES_PICK_ID = "roles_pick"
INTRODUCE_MODAL_ID = "introduce_modal"
INTRO_FIELD_NAME = "intro_name"
INTRO_FIELD_ABOUT = "intro_about"
INTRO_FIELD_INTERESTS = "intro_interests"


def _settings(ctx: InteractionContext) -> Settings:
    if not isinstance(ctx.settings, Settings):
        msg = "Heimdal handlers require heimdal.settings.Settings"
        raise TypeError(msg)
    return ctx.settings


# --------------------------------------------------------------------- /welcome


@router.command("welcome")
async def welcome(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Post the welcome card with an accept-rules button targeted at one member."""
    settings = _settings(ctx)
    target_id = str(interaction.option("user") or interaction.invoking_user.id)
    buttons = [
        responses.button(
            ctx.t("welcome.accept_button", interaction),
            custom_id=f"{RULES_ACCEPT_PREFIX}{target_id}",
            style=ButtonStyle.SUCCESS,
        )
    ]
    if settings.heimdal_rules_url:
        buttons.append(
            responses.button(
                ctx.t("welcome.rules_link", interaction),
                style=ButtonStyle.LINK,
                url=settings.heimdal_rules_url,
            )
        )
    return responses.message(
        components=[
            responses.container(
                responses.text_display(ctx.t("welcome.title", interaction)),
                responses.text_display(ctx.t("welcome.body", interaction, user=f"<@{target_id}>")),
                responses.separator(),
                responses.action_row(*buttons),
            )
        ],
        components_v2=True,
        allowed_mentions={"users": [target_id]},
    )


@router.component(RULES_ACCEPT_PREFIX)
async def rules_accept(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Grant the member role when the targeted member clicks the button."""
    settings = _settings(ctx)
    target_id = (interaction.custom_id or "").removeprefix(RULES_ACCEPT_PREFIX)
    clicker = interaction.invoking_user

    if clicker.id != target_id:
        return responses.ephemeral(
            ctx.t("welcome.not_for_you", interaction, user=f"<@{target_id}>")
        )

    if settings.heimdal_member_role_id and interaction.guild_id:
        try:
            await ctx.client.add_member_role(
                interaction.guild_id,
                clicker.id,
                settings.heimdal_member_role_id,
                reason="Heimdal: rules accepted",
            )
        except DiscordAPIError as exc:
            log.warning("member_role_failed", user_id=clicker.id, error=str(exc))
            return responses.ephemeral(ctx.t("welcome.role_failed", interaction))

    return responses.update_message(
        components=[
            responses.container(
                responses.text_display(ctx.t("welcome.title", interaction)),
                responses.text_display(
                    ctx.t("welcome.accepted", interaction, user=f"<@{clicker.id}>")
                ),
            )
        ],
        components_v2=True,
        allowed_mentions={"users": [clicker.id]},
    )


# ----------------------------------------------------------------------- /roles


@router.command("roles")
async def roles(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Show an ephemeral multi-select with the configured interest roles."""
    settings = _settings(ctx)
    available = settings.interest_roles()
    if not available:
        return responses.ephemeral(ctx.t("roles.not_configured", interaction))
    member_roles = set(interaction.member.roles) if interaction.member else set()
    options = [
        responses.select_option(role.label, role.role_id, default=role.role_id in member_roles)
        for role in available
    ]
    return responses.ephemeral(
        ctx.t("roles.prompt", interaction),
        components=[
            responses.action_row(
                responses.string_select(
                    ROLES_PICK_ID,
                    options,
                    placeholder=ctx.t("roles.placeholder", interaction),
                    min_values=0,
                    max_values=len(options),
                )
            )
        ],
    )


@router.component(ROLES_PICK_ID)
async def roles_pick(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Add the selected interest roles to the member (only configured roles are accepted)."""
    settings = _settings(ctx)
    allowed = {role.role_id: role.label for role in settings.interest_roles()}
    selected = [
        value for value in (interaction.data.values if interaction.data else []) if value in allowed
    ]
    if not interaction.guild_id:
        return responses.update_message(ctx.t("roles.guild_only", interaction), components=[])

    granted: list[str] = []
    for role_id in selected:
        try:
            await ctx.client.add_member_role(
                interaction.guild_id,
                interaction.invoking_user.id,
                role_id,
                reason="Heimdal: /roles self-assign",
            )
            granted.append(allowed[role_id])
        except DiscordAPIError as exc:
            log.warning("interest_role_failed", role_id=role_id, error=str(exc))

    if not granted:
        return responses.update_message(ctx.t("roles.none", interaction), components=[])
    return responses.update_message(
        ctx.t("roles.granted", interaction, roles=", ".join(granted)), components=[]
    )


# ------------------------------------------------------------------- /introduce


@router.command("introduce")
async def introduce(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Open the introduction modal."""
    return responses.modal(
        INTRODUCE_MODAL_ID,
        ctx.t("introduce.title", interaction),
        [
            responses.label(
                ctx.t("introduce.name_label", interaction),
                responses.text_input(INTRO_FIELD_NAME, max_length=64),
            ),
            responses.label(
                ctx.t("introduce.about_label", interaction),
                responses.text_input(
                    INTRO_FIELD_ABOUT, style=TextInputStyle.PARAGRAPH, max_length=1000
                ),
            ),
            responses.label(
                ctx.t("introduce.interests_label", interaction),
                responses.text_input(INTRO_FIELD_INTERESTS, required=False, max_length=200),
            ),
        ],
    )


@router.modal(INTRODUCE_MODAL_ID)
async def introduce_submit(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Publish the introduction card (same channel or the configured intro channel)."""
    settings = _settings(ctx)
    values = interaction.modal_values()
    user = interaction.invoking_user
    name = str(values.get(INTRO_FIELD_NAME) or user.display_name)
    about = str(values.get(INTRO_FIELD_ABOUT) or "")
    interests = str(values.get(INTRO_FIELD_INTERESTS) or "")

    blocks = [
        responses.text_display(
            ctx.t("introduce.card_title", interaction, user=f"<@{user.id}>", name=name)
        ),
        responses.text_display(about),
    ]
    if interests:
        blocks.append(
            responses.text_display(
                ctx.t("introduce.card_interests", interaction, interests=interests)
            )
        )
    card = {
        "components": [responses.container(*blocks)],
        "flags": int(responses.MessageFlags.IS_COMPONENTS_V2),
        "allowed_mentions": {"users": [user.id]},
    }

    target_channel = settings.heimdal_intro_channel_id
    if target_channel and target_channel != interaction.channel_id:
        try:
            await ctx.client.create_message(target_channel, card)
        except DiscordAPIError as exc:
            log.warning("intro_post_failed", channel_id=target_channel, error=str(exc))
            return responses.ephemeral(ctx.t("introduce.post_failed", interaction))
        return responses.ephemeral(
            ctx.t("introduce.posted_elsewhere", interaction, channel=f"<#{target_channel}>")
        )

    return responses.message(
        components=card["components"],
        components_v2=True,
        allowed_mentions={"users": [user.id]},
    )
