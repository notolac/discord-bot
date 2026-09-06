"""Heimdal settings (env vars prefixed ``HEIMDAL_``)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from discord_core import DiscordSettings
from heimdal.roles import ApprovalKey


@dataclass(frozen=True, slots=True)
class InterestRole:
    """One self-assignable cosmetic role shown in ``/roles``."""

    label: str
    role_id: str


class Settings(DiscordSettings):
    """Environment configuration for Heimdal."""

    heimdal_member_role_id: str | None = Field(
        default=None, description="Role granted when a member accepts the rules"
    )
    heimdal_interest_roles: str = Field(
        default="",
        description='Cosmetic self-assignable roles as "Label:ROLE_ID,..." (max 25)',
    )
    heimdal_rules_url: str | None = Field(
        default=None, description="Optional link shown next to the accept button"
    )
    heimdal_intro_channel_id: str | None = Field(
        default=None, description="Channel where introductions are posted (default: same channel)"
    )
    heimdal_approval_channel_id: str | None = Field(
        default=None, description="Staff channel for claimed-role approval cards"
    )
    heimdal_approver_role_ids: str = Field(
        default="",
        description="Comma-separated role ids that may Approve/Deny (e.g. admin, moderator)",
    )
    heimdal_organizer_role_id: str | None = Field(
        default=None, description="organizer role; granted only after staff approval"
    )
    heimdal_speaker_role_id: str | None = Field(
        default=None, description="speaker role; granted only after staff approval"
    )
    heimdal_startups_role_id: str | None = Field(
        default=None, description="Startups affiliation; granted only after staff approval"
    )
    heimdal_enterprises_role_id: str | None = Field(
        default=None, description="Enterprises affiliation; granted only after staff approval"
    )
    heimdal_denied_role_ids: str = Field(
        default="",
        description="Comma-separated ids Heimdal must never grant (admin, moderator, bots, …)",
    )

    def denied_role_ids(self) -> frozenset[str]:
        """Ids that must never be granted, plus @everyone (guild id) when configured."""
        ids = set(_parse_id_list(self.heimdal_denied_role_ids))
        if self.discord_prod_guild_id and self.discord_prod_guild_id.isdigit():
            ids.add(self.discord_prod_guild_id)
        if self.discord_dev_guild_id and self.discord_dev_guild_id.isdigit():
            ids.add(self.discord_dev_guild_id)
        return frozenset(ids)

    def approver_role_ids(self) -> frozenset[str]:
        """Role ids that count as staff for Approve/Deny (not filtered by the denylist)."""
        return frozenset(_parse_id_list(self.heimdal_approver_role_ids))

    def assignable_member_role_id(self) -> str | None:
        """Member role id if it is a snowflake and not on the denylist."""
        role_id = (self.heimdal_member_role_id or "").strip()
        if not role_id.isdigit() or role_id in self.denied_role_ids():
            return None
        return role_id

    def approval_role_map(self) -> dict[ApprovalKey, str]:
        """Approval-key → role id. Skips empty, non-digit, denied, and member-role ids."""
        raw = {
            ApprovalKey.ORGANIZER: self.heimdal_organizer_role_id,
            ApprovalKey.SPEAKER: self.heimdal_speaker_role_id,
            ApprovalKey.STARTUPS: self.heimdal_startups_role_id,
            ApprovalKey.ENTERPRISES: self.heimdal_enterprises_role_id,
        }
        denied = self.denied_role_ids()
        member_id = self.assignable_member_role_id()
        mapping: dict[ApprovalKey, str] = {}
        used: set[str] = set()
        for key, value in raw.items():
            role_id = (value or "").strip()
            if not role_id.isdigit() or role_id in denied or role_id == member_id:
                continue
            if role_id in used:
                continue
            used.add(role_id)
            mapping[key] = role_id
        return mapping

    def interest_roles(self) -> list[InterestRole]:
        """Parse cosmetic interest roles; skip anything not on that allowlist.

        Entries whose id is denied, the member role, an approval role, or a staff
        (approver) role are dropped so ``/roles`` cannot grant privileged ids even
        if they were left in ``HEIMDAL_INTEREST_ROLES``.
        """
        blocked = set(self.denied_role_ids())
        blocked.update(self.approver_role_ids())
        blocked.update(self.approval_role_map().values())
        member_id = self.assignable_member_role_id()
        if member_id:
            blocked.add(member_id)
        if self.heimdal_member_role_id and self.heimdal_member_role_id.isdigit():
            blocked.add(self.heimdal_member_role_id)

        roles: list[InterestRole] = []
        seen: set[str] = set()
        for chunk in self.heimdal_interest_roles.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            label, _, role_id = chunk.partition(":")
            label, role_id = label.strip(), role_id.strip()
            if not label or not role_id.isdigit() or role_id in blocked or role_id in seen:
                continue
            seen.add(role_id)
            roles.append(InterestRole(label=label, role_id=role_id))
        return roles[:25]


def _parse_id_list(raw: str) -> list[str]:
    ids: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.append(chunk)
    return ids
