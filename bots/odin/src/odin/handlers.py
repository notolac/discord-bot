"""Odin interaction handlers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from discord_core import DiscordAPIError, InteractionContext, Router, responses
from discord_core.interactions import ButtonStyle, Interaction
from odin.services.report_log import ModerationRecord, ReportLog
from odin.settings import Settings

router = Router()
log = structlog.get_logger("odin")

PURGE_CONFIRM_PREFIX = "purge_confirm_"
PURGE_CANCEL_ID = "purge_cancel"


def _settings(ctx: InteractionContext) -> Settings:
    if not isinstance(ctx.settings, Settings):
        msg = "Odin handlers require odin.settings.Settings"
        raise TypeError(msg)
    return ctx.settings


def _report_log(ctx: InteractionContext) -> ReportLog:
    return ReportLog(_settings(ctx).odin_reports_dir)


async def _notify_mods(ctx: InteractionContext, content: str) -> None:
    """Best-effort post to the moderators channel (never fails the interaction)."""
    channel_id = _settings(ctx).odin_mod_channel_id
    if not channel_id:
        return
    try:
        await ctx.client.create_message(
            channel_id, {"content": content, "allowed_mentions": {"parse": []}}
        )
    except DiscordAPIError as exc:
        log.warning("mod_channel_post_failed", channel_id=channel_id, error=str(exc))


# ------------------------------------------------------------------------ /warn


@router.command("warn")
async def warn(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Record a warning and notify the moderators channel."""
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    target_id = str(interaction.option("user"))
    reason = str(interaction.option("reason") or "")
    moderator = interaction.invoking_user

    _report_log(ctx).append(
        ModerationRecord(
            action="warn",
            guild_id=interaction.guild_id,
            moderator_id=moderator.id,
            target_id=target_id,
            reason=reason,
            channel_id=interaction.channel_id,
        )
    )
    await _notify_mods(
        ctx,
        ctx.t(
            "warn.mod_notice",
            interaction,
            target=f"<@{target_id}>",
            moderator=f"<@{moderator.id}>",
            reason=reason,
        ),
    )
    return responses.ephemeral(
        ctx.t("warn.done", interaction, target=f"<@{target_id}>", reason=reason)
    )


# --------------------------------------------------------------------- /timeout


@router.command("timeout")
async def timeout(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Apply a communication timeout via ``PATCH /guilds/{g}/members/{u}``."""
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    target_id = str(interaction.option("user"))
    minutes = int(interaction.option("minutes") or 0)
    reason = str(interaction.option("reason") or "")
    until = datetime.now(UTC) + timedelta(minutes=minutes)

    try:
        await ctx.client.modify_guild_member(
            interaction.guild_id,
            target_id,
            {"communication_disabled_until": until.isoformat(timespec="seconds")},
            reason=f"Odin /timeout by {interaction.invoking_user.id}: {reason}"[:512],
        )
    except DiscordAPIError as exc:
        log.warning("timeout_failed", target_id=target_id, error=str(exc))
        return responses.ephemeral(ctx.t("timeout.failed", interaction, error=exc.message))

    _report_log(ctx).append(
        ModerationRecord(
            action="timeout",
            guild_id=interaction.guild_id,
            moderator_id=interaction.invoking_user.id,
            target_id=target_id,
            reason=reason,
            channel_id=interaction.channel_id,
            extra={"minutes": minutes, "until": until.isoformat(timespec="seconds")},
        )
    )
    until_ts = int(until.timestamp())
    await _notify_mods(
        ctx,
        ctx.t(
            "timeout.mod_notice",
            interaction,
            target=f"<@{target_id}>",
            moderator=f"<@{interaction.invoking_user.id}>",
            minutes=minutes,
            until=f"<t:{until_ts}:R>",
            reason=reason or "—",
        ),
    )
    return responses.ephemeral(
        ctx.t(
            "timeout.done",
            interaction,
            target=f"<@{target_id}>",
            minutes=minutes,
            until=f"<t:{until_ts}:R>",
        )
    )


# ----------------------------------------------------------------------- /purge


@router.command("purge")
async def purge(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Ask for confirmation before deleting messages (destructive)."""
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    count = int(interaction.option("count") or 0)
    return responses.ephemeral(
        ctx.t("purge.confirm", interaction, count=count),
        components=[
            responses.action_row(
                responses.button(
                    ctx.t("purge.confirm_button", interaction, count=count),
                    custom_id=f"{PURGE_CONFIRM_PREFIX}{count}",
                    style=ButtonStyle.DANGER,
                ),
                responses.button(
                    ctx.t("purge.cancel_button", interaction),
                    custom_id=PURGE_CANCEL_ID,
                    style=ButtonStyle.SECONDARY,
                ),
            )
        ],
    )


@router.component(PURGE_CANCEL_ID)
async def purge_cancel(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Cancel: replace the confirmation with a notice and drop the buttons."""
    return responses.update_message(ctx.t("purge.cancelled", interaction), components=[])


@router.component(PURGE_CONFIRM_PREFIX, defer=True)
async def purge_confirm(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Deferred: fetch the last N messages, bulk-delete them, then edit the confirmation."""
    count = int((interaction.custom_id or "").removeprefix(PURGE_CONFIRM_PREFIX) or 0)
    channel_id = interaction.channel_id
    if not channel_id or not interaction.guild_id or count < 1:
        return responses.update_message(ctx.t("purge.cancelled", interaction), components=[])

    try:
        messages = await ctx.client.get_channel_messages(channel_id, limit=count)
        # Bulk delete rejects messages older than 14 days; skip them.
        cutoff = datetime.now(UTC) - timedelta(days=14)
        ids = (
            [m["id"] for m in messages if datetime.fromisoformat(m["timestamp"]) > cutoff]
            if messages and "timestamp" in messages[0]
            else [m["id"] for m in messages]
        )
        if ids:
            await ctx.client.bulk_delete_messages(
                channel_id, ids, reason=f"Odin /purge by {interaction.invoking_user.id}"
            )
    except DiscordAPIError as exc:
        log.warning("purge_failed", channel_id=channel_id, error=str(exc))
        return responses.update_message(
            ctx.t("purge.failed", interaction, error=exc.message), components=[]
        )

    _report_log(ctx).append(
        ModerationRecord(
            action="purge",
            guild_id=interaction.guild_id,
            moderator_id=interaction.invoking_user.id,
            channel_id=channel_id,
            extra={"requested": count, "deleted": len(ids)},
        )
    )
    return responses.update_message(
        ctx.t("purge.done", interaction, deleted=len(ids)), components=[]
    )


# ------------------------------------------------------------- "Report message"


@router.command("Report message")
async def report_message(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Forward a message to the moderators channel and record the report."""
    settings = _settings(ctx)
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    if not settings.odin_mod_channel_id:
        return responses.ephemeral(ctx.t("report.not_configured", interaction))

    target_id = interaction.data.target_id if interaction.data else None
    message = interaction.resolved_message(target_id) if target_id else None
    if message is None:
        return responses.ephemeral(ctx.t("report.missing", interaction))

    author_id = message.author.id if message.author else "?"
    jump = f"https://discord.com/channels/{interaction.guild_id}/{message.channel_id or interaction.channel_id}/{message.id}"
    excerpt = (message.content or "").strip()
    if len(excerpt) > 300:
        excerpt = excerpt[:297] + "…"

    _report_log(ctx).append(
        ModerationRecord(
            action="report",
            guild_id=interaction.guild_id,
            moderator_id=interaction.invoking_user.id,
            target_id=author_id,
            channel_id=message.channel_id or interaction.channel_id,
            extra={"message_id": message.id, "excerpt": excerpt},
        )
    )
    await _notify_mods(
        ctx,
        ctx.t(
            "report.mod_notice",
            interaction,
            reporter=f"<@{interaction.invoking_user.id}>",
            author=f"<@{author_id}>",
            link=jump,
            excerpt=excerpt or "—",
        ),
    )
    return responses.ephemeral(ctx.t("report.done", interaction))


# ---------------------------------------------------------------- "View history"


@router.command("View history")
async def view_history(interaction: Interaction, ctx: InteractionContext) -> dict[str, Any]:
    """Show the last moderation records about the targeted member (ephemeral)."""
    settings = _settings(ctx)
    if not interaction.guild_id:
        return responses.ephemeral(ctx.t("common.guild_only", interaction))
    target_id = (interaction.data.target_id if interaction.data else None) or ""
    records = _report_log(ctx).for_target(
        interaction.guild_id, target_id, limit=settings.odin_history_limit
    )
    if not records:
        return responses.ephemeral(ctx.t("history.empty", interaction, target=f"<@{target_id}>"))

    lines = [ctx.t("history.header", interaction, target=f"<@{target_id}>", count=len(records))]
    for record in records:
        ts = int(datetime.fromisoformat(record.timestamp).timestamp())
        detail = record.reason or record.extra.get("excerpt") or ""
        lines.append(
            f"• <t:{ts}:d> **{record.action}** by <@{record.moderator_id}> — {detail}".rstrip(" —")
        )
    return responses.ephemeral("\n".join(lines))
