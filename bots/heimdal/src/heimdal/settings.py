"""Heimdal settings (env vars prefixed ``HEIMDAL_``)."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import Field

from discord_core import DiscordSettings


@dataclass(frozen=True, slots=True)
class InterestRole:
    """One self-assignable role shown in ``/roles``."""

    label: str
    role_id: str


class Settings(DiscordSettings):
    """Environment configuration for Heimdal."""

    heimdal_member_role_id: str | None = Field(
        default=None, description="Role granted when a member accepts the rules"
    )
    heimdal_interest_roles: str = Field(
        default="",
        description='Self-assignable roles as "Label:ROLE_ID,Label2:ROLE_ID2" (max 25)',
    )
    heimdal_rules_url: str | None = Field(
        default=None, description="Optional link shown next to the accept button"
    )
    heimdal_intro_channel_id: str | None = Field(
        default=None, description="Channel where introductions are posted (default: same channel)"
    )

    def interest_roles(self) -> list[InterestRole]:
        """Parse ``heimdal_interest_roles`` into a list (invalid entries are skipped)."""
        roles: list[InterestRole] = []
        for chunk in self.heimdal_interest_roles.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            label, _, role_id = chunk.partition(":")
            label, role_id = label.strip(), role_id.strip()
            if label and role_id.isdigit():
                roles.append(InterestRole(label=label, role_id=role_id))
        return roles[:25]
