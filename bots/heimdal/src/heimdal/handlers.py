"""Heimdal interaction handlers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from discord_core import DiscordAPIError, InteractionContext, Router, responses
from discord_core.interactions import ButtonStyle, Interaction, MessageFlags, TextInputStyle
from heimdal.roles import (
    KEY_AUDIT_LABEL,
    KEY_I18N,
    ROLE_ASK_ID,
    ROLE_NO_PREFIX,
    ROLE_OK_PREFIX,
    ROLE_REQ_PREFIX,
    RULES_ACCEPT_PUBLIC_ID,
    RULES_ACCEPT_TARGET_PREFIX,
    ApprovalKey,
    approval_button_id,
    clicker_is_staff,
    is_snowflake,
    parse_approval_button,
    parse_request_modal_id,
    parse_role_request_value,
    request_modal_id,
)
from heimdal.settings import Settings

router = Router()
log = structlog.get_logger("heimdal")

ROLES_PICK_ID = "roles_pick"
INTRODUCE_MODAL_ID = "introduce_modal"
INTRO_FIELD_NAME = "intro_name"
INTRO_FIELD_ABOUT = "intro_about"
INTRO_FIELD_INTERESTS = "intro_interests"
REQ_FIELD_AFFILIATION = "req_aff"
REQ_FIELD_EVIDENCE = "req_note"


def _settings(ctx: InteractionContext) -> Settings:
    if not isinstance(ctx.settings, Settings):
        msg = "Heimdal handlers require heimdal.settings.Settings"
        raise TypeError(msg)
    return ctx.settings


def _user_mentions(*user_ids: str) -> dict[str, Any]:
    """``allowed_mentions`` with parse disabled and only the given user snowflakes."""
    users: list[str] = []
    seen: set[str] = set()
    for uid in user_ids:
        if is_snowflake(uid) and uid not in seen:
            seen.add(uid)
            users.append(uid)
    return {"parse": [], "users": users}


def _role_label(key: ApprovalKey, interaction: Interaction, ctx: InteractionContext) -> str:
    return ctx.t(KEY_I18N[key], interaction)


# --------------------------------------------------------------------- /welcome


def _accept_buttons(
    interaction: Interaction, ctx: InteractionContext, custom_id: str
) -> list[dict[str, Any]]:
    settings = _settings(ctx)
    buttons = [
        responses.button(
            ctx.t("welcome.accept_button", interaction),
            custom_id=custom_id,
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
    return buttons


def _request_select(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any] | None:
    mapping = _settings(ctx).approval_role_map()
    if not mapping:
        return None
    options = [
        responses.select_option(_role_label(key, interaction, ctx), key.value) for key in mapping
    ]
    return responses.string_select(
        ROLE_ASK_ID,
        options,
        placeholder=ctx.t("request.select_placeholder", interaction),
        min_values=1,
        max_values=1,
    )


def _public_welcome_card(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = [
        responses.text_display(ctx.t("welcome.public_title", interaction)),
        responses.text_display(ctx.t("welcome.public_body", interaction)),
        responses.separator(),
        responses.action_row(*_accept_buttons(interaction, ctx, RULES_ACCEPT_PUBLIC_ID)),
    ]
    select = _request_select(interaction, ctx)
    if select is not None:
        blocks.append(responses.text_display(ctx.t("request.select_prompt", interaction)))
        blocks.append(responses.action_row(select))
    return responses.message(
        components=[responses.container(*blocks)],
        components_v2=True,
        allowed_mentions=_user_mentions(),
    )


@router.command("welcome")
async def welcome(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Post a public onboarding card, or a targeted card when ``user`` is given."""
    target = interaction.option("user")
    if not target:
        return _public_welcome_card(interaction, ctx)

    target_id = str(target)
    return responses.message(
        components=[
            responses.container(
                responses.text_display(ctx.t("welcome.title", interaction)),
                responses.text_display(ctx.t("welcome.body", interaction, user=f"<@{target_id}>")),
                responses.separator(),
                responses.action_row(
                    *_accept_buttons(interaction, ctx, f"{RULES_ACCEPT_TARGET_PREFIX}{target_id}")
                ),
            )
        ],
        components_v2=True,
        allowed_mentions=_user_mentions(target_id),
    )


async def _grant_member_role(
    interaction: Interaction, ctx: InteractionContext, user_id: str
) -> dict[str, Any] | None:
    """PUT the configured member role. Returns an ephemeral error payload, or None on success.

    The role id is taken only from settings. Client values and ``custom_id`` snowflakes
    other than the (already authorised) recipient are ignored.
    """
    settings = _settings(ctx)
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    role_id = settings.assignable_member_role_id()
    if not role_id:
        return None
    member_roles = set(interaction.member.roles) if interaction.member else set()
    if role_id in member_roles:
        return None
    try:
        await ctx.client.add_member_role(
            interaction.guild_id,
            user_id,
            role_id,
            reason="Heimdal: rules accepted",
        )
    except DiscordAPIError as exc:
        log.warning("member_role_failed", user_id=user_id, error=str(exc))
        return responses.ephemeral(ctx.t("welcome.role_failed", interaction))
    return None


@router.component(RULES_ACCEPT_TARGET_PREFIX)
async def rules_accept_targeted(
    interaction: Interaction, ctx: InteractionContext
) -> dict[str, Any]:
    """Grant the member role when the targeted member clicks ``rules_accept_<id>``."""
    target_id = (interaction.custom_id or "").removeprefix(RULES_ACCEPT_TARGET_PREFIX)
    clicker = interaction.invoking_user
    if not is_snowflake(target_id) or clicker.id != target_id:
        mentioned = f"<@{target_id}>" if is_snowflake(target_id) else target_id
        return responses.ephemeral(ctx.t("welcome.not_for_you", interaction, user=mentioned))

    error = await _grant_member_role(interaction, ctx, clicker.id)
    if error is not None:
        return error

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
        allowed_mentions=_user_mentions(clicker.id),
    )


@router.component(RULES_ACCEPT_PUBLIC_ID)
async def rules_accept_public(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Grant the member role to the clicker from the persistent public card.

    The public ``custom_id`` encodes no user id. The recipient is always
    ``interaction.invoking_user.id``. The persistent card is not edited.
    """
    clicker = interaction.invoking_user
    error = await _grant_member_role(interaction, ctx, clicker.id)
    if error is not None:
        return error
    return responses.ephemeral(
        ctx.t("welcome.accepted_ephemeral", interaction, user=f"<@{clicker.id}>")
    )


# --------------------------------------------------------------- /request-role


def _request_modal(
    interaction: Interaction, ctx: InteractionContext, key: ApprovalKey
) -> dict[str, Any]:
    label = _role_label(key, interaction, ctx)
    return responses.modal(
        request_modal_id(key),
        ctx.t("request.modal_title", interaction, role=label),
        [
            responses.label(
                ctx.t("request.affiliation_label", interaction),
                responses.text_input(REQ_FIELD_AFFILIATION, max_length=100),
                description=ctx.t("request.affiliation_description", interaction),
            ),
            responses.label(
                ctx.t("request.evidence_label", interaction),
                responses.text_input(
                    REQ_FIELD_EVIDENCE, style=TextInputStyle.PARAGRAPH, max_length=300
                ),
                description=ctx.t("request.evidence_description", interaction),
            ),
        ],
    )


def _begin_role_request(
    interaction: Interaction, ctx: InteractionContext, raw_value: str
) -> dict[str, Any]:
    settings = _settings(ctx)
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    if not settings.heimdal_approval_channel_id:
        return responses.ephemeral(ctx.t("request.not_configured", interaction))
    key = parse_role_request_value(raw_value)
    if key is None or key not in settings.approval_role_map():
        return responses.ephemeral(ctx.t("request.unknown_role", interaction))
    return _request_modal(interaction, ctx, key)


@router.command("request-role")
async def request_role(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Open the evidence modal for a claimed role (fixed enum choices only)."""
    return _begin_role_request(interaction, ctx, str(interaction.option("role") or ""))


@router.component(ROLE_ASK_ID)
async def role_ask(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Open the evidence modal from the public onboarding select (enum keys only)."""
    values = interaction.data.values if interaction.data else []
    raw = str(values[0]) if values else ""
    return _begin_role_request(interaction, ctx, raw)


def _staff_card_payload(
    interaction: Interaction,
    ctx: InteractionContext,
    *,
    key: ApprovalKey,
    requester_id: str,
    affiliation: str,
    evidence: str,
    requested_at: int,
) -> dict[str, Any]:
    label = _role_label(key, interaction, ctx)
    return {
        "components": [
            responses.container(
                responses.text_display(ctx.t("request.staff_title", interaction)),
                responses.text_display(
                    ctx.t(
                        "request.staff_body",
                        interaction,
                        user=f"<@{requester_id}>",
                        role=label,
                    )
                ),
                responses.text_display(
                    ctx.t("request.staff_affiliation", interaction, affiliation=affiliation)
                ),
                responses.text_display(
                    ctx.t("request.staff_evidence", interaction, evidence=evidence)
                ),
                responses.text_display(ctx.t("request.staff_time", interaction, ts=requested_at)),
                responses.separator(),
                responses.action_row(
                    responses.button(
                        ctx.t("request.approve", interaction),
                        custom_id=approval_button_id(True, key, requester_id),
                        style=ButtonStyle.SUCCESS,
                    ),
                    responses.button(
                        ctx.t("request.deny", interaction),
                        custom_id=approval_button_id(False, key, requester_id),
                        style=ButtonStyle.DANGER,
                    ),
                ),
            )
        ],
        "flags": int(MessageFlags.IS_COMPONENTS_V2),
        "allowed_mentions": _user_mentions(requester_id),
    }


def _resolved_staff_card_body(
    interaction: Interaction,
    ctx: InteractionContext,
    *,
    approved: bool,
    key: ApprovalKey,
    requester_id: str,
    staff_id: str,
    affiliation: str,
    evidence: str,
) -> dict[str, Any]:
    """PATCH body for the staff card after Approve/Deny (not an interaction callback)."""
    label = _role_label(key, interaction, ctx)
    status_key = "request.approved" if approved else "request.denied"
    return {
        "components": [
            responses.container(
                responses.text_display(ctx.t("request.staff_title", interaction)),
                responses.text_display(
                    ctx.t(
                        status_key,
                        interaction,
                        role=label,
                        user=f"<@{requester_id}>",
                        staff=f"<@{staff_id}>",
                    )
                ),
                responses.text_display(
                    ctx.t("request.staff_affiliation", interaction, affiliation=affiliation)
                ),
                responses.text_display(
                    ctx.t("request.staff_evidence", interaction, evidence=evidence)
                ),
            )
        ],
        "flags": int(MessageFlags.IS_COMPONENTS_V2),
        "allowed_mentions": _user_mentions(requester_id, staff_id),
    }


async def _edit_staff_card(
    interaction: Interaction, ctx: InteractionContext, body: dict[str, Any]
) -> None:
    channel_id = interaction.channel_id
    message_id = interaction.message.id if interaction.message is not None else None
    if not channel_id or not message_id:
        log.warning("staff_card_edit_skipped", reason="missing_message")
        return
    try:
        await ctx.client.edit_message(channel_id, message_id, body)
    except DiscordAPIError as exc:
        log.warning("staff_card_edit_failed", channel_id=channel_id, error=str(exc))


def _evidence_from_modal(interaction: Interaction) -> tuple[str, str]:
    values = interaction.modal_values()
    affiliation = str(values.get(REQ_FIELD_AFFILIATION) or "").strip() or "—"
    evidence = str(values.get(REQ_FIELD_EVIDENCE) or "").strip() or "—"
    return affiliation[:100], evidence[:300]


@router.modal(ROLE_REQ_PREFIX)
async def role_request_submit(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Post an approval card in the staff channel; ACK the requester ephemerally."""
    settings = _settings(ctx)
    key = parse_request_modal_id(interaction.custom_id or "")
    if key is None or key not in settings.approval_role_map():
        return responses.ephemeral(ctx.t("request.unknown_role", interaction))
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    channel_id = settings.heimdal_approval_channel_id
    if not channel_id:
        return responses.ephemeral(ctx.t("request.not_configured", interaction))

    requester = interaction.invoking_user
    affiliation, evidence = _evidence_from_modal(interaction)
    card = _staff_card_payload(
        interaction,
        ctx,
        key=key,
        requester_id=requester.id,
        affiliation=affiliation,
        evidence=evidence,
        requested_at=int(datetime.now(UTC).timestamp()),
    )
    try:
        await ctx.client.create_message(channel_id, card)
    except DiscordAPIError as exc:
        log.warning("approval_post_failed", channel_id=channel_id, error=str(exc))
        return responses.ephemeral(ctx.t("request.post_failed", interaction))
    log.info("role_request_submitted", user_id=requester.id, key=key.value)
    return responses.ephemeral(ctx.t("request.sent", interaction))


@router.component(ROLE_OK_PREFIX, defer=True, ephemeral=True)
async def role_approve(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Staff-only: grant the mapped approval role to the encoded requester."""
    return await _resolve_approval(interaction, ctx, expect_approved=True)


@router.component(ROLE_NO_PREFIX, defer=True, ephemeral=True)
async def role_deny(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Staff-only: deny without granting a role."""
    return await _resolve_approval(interaction, ctx, expect_approved=False)


async def _resolve_approval(
    interaction: Interaction, ctx: InteractionContext, *, expect_approved: bool
) -> dict[str, Any]:
    parsed = parse_approval_button(interaction.custom_id or "")
    if parsed is None:
        return responses.ephemeral(ctx.t("request.bad_button", interaction))
    approved, key, requester_id = parsed
    if approved != expect_approved:
        return responses.ephemeral(ctx.t("request.bad_button", interaction))
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    if interaction.member is None or not clicker_is_staff(interaction, _settings(ctx)):
        return responses.ephemeral(ctx.t("request.not_staff", interaction))

    settings = _settings(ctx)
    staff_id = interaction.invoking_user.id
    affiliation, evidence = "—", "—"
    label = _role_label(key, interaction, ctx)

    if not approved:
        await _edit_staff_card(
            interaction,
            ctx,
            _resolved_staff_card_body(
                interaction,
                ctx,
                approved=False,
                key=key,
                requester_id=requester_id,
                staff_id=staff_id,
                affiliation=affiliation,
                evidence=evidence,
            ),
        )
        log.info("role_request_denied", requester_id=requester_id, key=key.value, staff_id=staff_id)
        return responses.ephemeral(
            ctx.t("request.denied_ack", interaction, role=label, user=f"<@{requester_id}>")
        )

    role_id = settings.approval_role_map().get(key)
    if role_id is None:
        return responses.ephemeral(ctx.t("request.unknown_role", interaction))

    try:
        await ctx.client.add_member_role(
            interaction.guild_id,
            requester_id,
            role_id,
            reason=f"Heimdal: approved {KEY_AUDIT_LABEL[key]} by {staff_id}"[:512],
        )
    except DiscordAPIError as exc:
        log.warning(
            "approval_role_failed",
            requester_id=requester_id,
            key=key.value,
            error=str(exc),
        )
        return responses.ephemeral(ctx.t("request.grant_failed", interaction))

    await _edit_staff_card(
        interaction,
        ctx,
        _resolved_staff_card_body(
            interaction,
            ctx,
            approved=True,
            key=key,
            requester_id=requester_id,
            staff_id=staff_id,
            affiliation=affiliation,
            evidence=evidence,
        ),
    )
    log.info("role_request_approved", requester_id=requester_id, key=key.value, staff_id=staff_id)
    return responses.ephemeral(
        ctx.t("request.approved_ack", interaction, role=label, user=f"<@{requester_id}>")
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
        "flags": int(MessageFlags.IS_COMPONENTS_V2),
        "allowed_mentions": _user_mentions(user.id),
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
        allowed_mentions=_user_mentions(user.id),
    )
