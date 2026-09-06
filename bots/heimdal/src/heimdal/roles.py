"""Allowlists, custom_id parsing and staff checks for Heimdal role grants.

Role snowflakes used in ``PUT /guilds/{g}/members/{u}/roles/{r}`` come from env
mappings after an enum key lookup — never from a raw client-supplied id.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from discord_core.interactions import Interaction, Permissions

if TYPE_CHECKING:
    from heimdal.settings import Settings

RULES_ACCEPT_PUBLIC_ID = "rules_accept"
RULES_ACCEPT_TARGET_PREFIX = "rules_accept_"
ROLE_ASK_ID = "role_ask"
ROLE_REQ_PREFIX = "role_req_"
ROLE_OK_PREFIX = "role_ok_"
ROLE_NO_PREFIX = "role_no_"

_STAFF_PERMISSIONS = Permissions.MANAGE_GUILD | Permissions.ADMINISTRATOR


class ApprovalKey(StrEnum):
    """Short enum stored in ``custom_id`` (never a role snowflake)."""

    ORGANIZER = "org"
    SPEAKER = "spk"
    STARTUPS = "stu"
    ENTERPRISES = "ent"


# Slash-command choice values → enum. Select menus use the enum value directly.
CHOICE_TO_KEY: dict[str, ApprovalKey] = {
    "organizer": ApprovalKey.ORGANIZER,
    "speaker": ApprovalKey.SPEAKER,
    "startups": ApprovalKey.STARTUPS,
    "enterprises": ApprovalKey.ENTERPRISES,
}

KEY_I18N: dict[ApprovalKey, str] = {
    ApprovalKey.ORGANIZER: "request.role_org",
    ApprovalKey.SPEAKER: "request.role_spk",
    ApprovalKey.STARTUPS: "request.role_stu",
    ApprovalKey.ENTERPRISES: "request.role_ent",
}

# English names for audit-log reasons (not localized).
KEY_AUDIT_LABEL: dict[ApprovalKey, str] = {
    ApprovalKey.ORGANIZER: "organizer",
    ApprovalKey.SPEAKER: "speaker",
    ApprovalKey.STARTUPS: "startups",
    ApprovalKey.ENTERPRISES: "enterprises",
}

_KEY_BY_VALUE = {key.value: key for key in ApprovalKey}


def is_snowflake(value: str) -> bool:
    """Return True if ``value`` is a non-empty digit-only Discord snowflake."""
    return bool(value) and value.isdigit()


def parse_role_request_value(value: str) -> ApprovalKey | None:
    """Map a command choice or select value to an approval key (None if unknown)."""
    if value in CHOICE_TO_KEY:
        return CHOICE_TO_KEY[value]
    return _KEY_BY_VALUE.get(value)


def request_modal_id(key: ApprovalKey) -> str:
    """``custom_id`` for the evidence modal (``role_req_<key>``)."""
    return f"{ROLE_REQ_PREFIX}{key.value}"


def parse_request_modal_id(custom_id: str) -> ApprovalKey | None:
    """Parse ``role_req_<key>``; unknown or malformed ids return None."""
    if not custom_id.startswith(ROLE_REQ_PREFIX):
        return None
    return _KEY_BY_VALUE.get(custom_id.removeprefix(ROLE_REQ_PREFIX))


def approval_button_id(approved: bool, key: ApprovalKey, user_id: str) -> str:
    """Build ``role_ok_<key>_<user_id>`` or ``role_no_<key>_<user_id>``."""
    prefix = ROLE_OK_PREFIX if approved else ROLE_NO_PREFIX
    return f"{prefix}{key.value}_{user_id}"


def parse_approval_button(custom_id: str) -> tuple[bool, ApprovalKey, str] | None:
    """Parse an Approve/Deny ``custom_id``.

    Returns ``(approved, key, requester_id)`` or None if the id is forged/unknown.
    The role snowflake is never present in the id — callers must map ``key``
    through the env allowlist.
    """
    if custom_id.startswith(ROLE_OK_PREFIX):
        approved = True
        rest = custom_id.removeprefix(ROLE_OK_PREFIX)
    elif custom_id.startswith(ROLE_NO_PREFIX):
        approved = False
        rest = custom_id.removeprefix(ROLE_NO_PREFIX)
    else:
        return None
    key_raw, sep, user_id = rest.partition("_")
    if not sep:
        return None
    key = _KEY_BY_VALUE.get(key_raw)
    if key is None or not is_snowflake(user_id):
        return None
    return approved, key, user_id


def clicker_is_staff(interaction: Interaction, settings: Settings) -> bool:
    """Return True if the clicker may Approve/Deny (staff role or MANAGE_GUILD).

    Missing ``member`` (DMs) always refuses. A random member clicking their own
    card fails this check; staff requesting a role for themselves may still
    approve it.
    """
    member = interaction.member
    if member is None:
        return False
    if settings.approver_role_ids() & set(member.roles):
        return True
    if not member.permissions:
        return False
    try:
        perms = int(member.permissions)
    except ValueError:
        return False
    return bool(perms & int(_STAFF_PERMISSIONS))
