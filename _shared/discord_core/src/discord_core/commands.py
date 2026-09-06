"""Typed application command declarations and idempotent registration.

Reference: https://docs.discord.com/developers/interactions/application-commands
Key facts encoded here:
* ``PUT`` bulk-overwrites the whole command set for a scope — commands not included are deleted.
* Guild commands update instantly (use for dev); global commands are cached.
* Names of ``CHAT_INPUT`` commands/options must be lowercase, 1–32 chars.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from discord_core.interactions import CommandType, ContextType, IntegrationType, OptionType

if TYPE_CHECKING:
    from discord_core.http import DiscordClient

_CHAT_INPUT_NAME = re.compile(r"^[-_\w]{1,32}$", re.UNICODE)


@dataclass(slots=True)
class Choice:
    """Fixed choice for STRING/INTEGER/NUMBER options."""

    name: str
    value: str | int | float
    name_localizations: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the API shape."""
        payload: dict[str, Any] = {"name": self.name, "value": self.value}
        if self.name_localizations:
            payload["name_localizations"] = self.name_localizations
        return payload


@dataclass(slots=True)
class Option:
    """Command option (parameter, subcommand or subcommand group)."""

    name: str
    description: str
    type: OptionType = OptionType.STRING
    required: bool = False
    choices: list[Choice] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    channel_types: list[int] | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    min_length: int | None = None
    max_length: int | None = None
    autocomplete: bool = False
    name_localizations: dict[str, str] | None = None
    description_localizations: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the API shape (omits empty/None fields)."""
        _validate_chat_input_name(self.name)
        payload: dict[str, Any] = {
            "type": int(self.type),
            "name": self.name,
            "description": self.description,
        }
        if (
            self.type not in (OptionType.SUB_COMMAND, OptionType.SUB_COMMAND_GROUP)
            and self.required
        ):
            payload["required"] = True
        if self.choices:
            payload["choices"] = [c.to_payload() for c in self.choices]
        if self.options:
            payload["options"] = [o.to_payload() for o in _required_first(self.options)]
        if self.channel_types:
            payload["channel_types"] = self.channel_types
        if self.min_value is not None:
            payload["min_value"] = self.min_value
        if self.max_value is not None:
            payload["max_value"] = self.max_value
        if self.min_length is not None:
            payload["min_length"] = self.min_length
        if self.max_length is not None:
            payload["max_length"] = self.max_length
        if self.autocomplete:
            if self.choices:
                msg = f"option {self.name!r}: autocomplete cannot be combined with choices"
                raise ValueError(msg)
            payload["autocomplete"] = True
        if self.name_localizations:
            payload["name_localizations"] = self.name_localizations
        if self.description_localizations:
            payload["description_localizations"] = self.description_localizations
        return payload


@dataclass(slots=True)
class Command:
    """Application command declaration."""

    name: str
    description: str = ""
    type: CommandType = CommandType.CHAT_INPUT
    options: list[Option] = field(default_factory=list)
    default_member_permissions: int | None = None
    nsfw: bool = False
    integration_types: list[IntegrationType] = field(
        default_factory=lambda: [IntegrationType.GUILD_INSTALL]
    )
    contexts: list[ContextType] = field(default_factory=lambda: [ContextType.GUILD])
    name_localizations: dict[str, str] | None = None
    description_localizations: dict[str, str] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Serialize to the API shape used by ``POST``/``PUT`` commands endpoints."""
        if self.type == CommandType.CHAT_INPUT:
            _validate_chat_input_name(self.name)
            if not 1 <= len(self.description) <= 100:
                msg = f"command {self.name!r}: description must be 1–100 chars"
                raise ValueError(msg)
        elif self.description:
            msg = f"command {self.name!r}: USER/MESSAGE commands must have an empty description"
            raise ValueError(msg)
        if len(self.options) > 25:
            msg = f"command {self.name!r}: at most 25 options"
            raise ValueError(msg)

        payload: dict[str, Any] = {
            "name": self.name,
            "type": int(self.type),
            "description": self.description,
            "integration_types": [int(i) for i in self.integration_types],
            "contexts": [int(c) for c in self.contexts],
        }
        if self.options:
            payload["options"] = [o.to_payload() for o in _required_first(self.options)]
        if self.default_member_permissions is not None:
            # Serialized as a string bitfield; "0" = admins only.
            payload["default_member_permissions"] = str(int(self.default_member_permissions))
        if self.nsfw:
            payload["nsfw"] = True
        if self.name_localizations:
            payload["name_localizations"] = self.name_localizations
        if self.description_localizations:
            payload["description_localizations"] = self.description_localizations
        return payload


def _validate_chat_input_name(name: str) -> None:
    if not _CHAT_INPUT_NAME.match(name) or name != name.lower():
        msg = f"invalid CHAT_INPUT name {name!r}: 1–32 chars, lowercase, [-_ letters digits]"
        raise ValueError(msg)


def _required_first(options: list[Option]) -> list[Option]:
    """Discord requires required options before optional ones."""
    return sorted(options, key=lambda o: not o.required)


# ------------------------------------------------------------------------ sync

_COMPARE_KEYS = (
    "name",
    "type",
    "description",
    "options",
    "default_member_permissions",
    "nsfw",
    "integration_types",
    "contexts",
    "name_localizations",
    "description_localizations",
)


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce an API command object to the comparable subset with stable defaults."""
    normalized: dict[str, Any] = {}
    for key in _COMPARE_KEYS:
        value = payload.get(key)
        if key == "type" and value is None:
            value = int(CommandType.CHAT_INPUT)
        if key == "options":
            value = [_normalize_option(o) for o in (value or [])]
        if key == "nsfw":
            value = bool(value)
        if key in ("name_localizations", "description_localizations") and not value:
            value = None
        if key in ("integration_types", "contexts") and value is not None:
            value = sorted(int(v) for v in value)
        normalized[key] = value
    return normalized


def _normalize_option(option: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "type",
        "name",
        "description",
        "required",
        "choices",
        "options",
        "channel_types",
        "min_value",
        "max_value",
        "min_length",
        "max_length",
        "autocomplete",
        "name_localizations",
        "description_localizations",
    )
    normalized: dict[str, Any] = {}
    for key in keys:
        value = option.get(key)
        if key in ("required", "autocomplete"):
            value = bool(value)
        elif key == "options":
            value = [_normalize_option(o) for o in (value or [])]
        elif key == "choices":
            value = [
                {k: v for k, v in c.items() if k in ("name", "value", "name_localizations") and v}
                for c in (value or [])
            ]
        elif not value:
            value = None
        normalized[key] = value
    return normalized


@dataclass(slots=True)
class CommandDiff:
    """Difference between the remote command set and the local declaration."""

    added: list[str]
    removed: list[str]
    changed: list[str]
    unchanged: list[str]

    @property
    def is_empty(self) -> bool:
        """``True`` when remote already matches local."""
        return not (self.added or self.removed or self.changed)

    def summary(self) -> str:
        """One-line human summary."""
        return (
            f"added={len(self.added)} removed={len(self.removed)} "
            f"changed={len(self.changed)} unchanged={len(self.unchanged)}"
        )


def diff_commands(remote: list[dict[str, Any]], local: list[Command]) -> CommandDiff:
    """Compare remote commands (API objects) with local declarations, keyed by ``(type, name)``."""
    remote_map = {(int(c.get("type", 1)), c["name"]): _normalize(c) for c in remote}
    local_map = {(int(c.type), c.name): _normalize(c.to_payload()) for c in local}

    added = [name for (_, name) in local_map if (_, name) not in remote_map]
    removed = [name for (_, name) in remote_map if (_, name) not in local_map]
    changed = [
        name
        for key, payload in local_map.items()
        if key in remote_map and remote_map[key] != payload
        for name in (key[1],)
    ]
    unchanged = [
        name
        for key, payload in local_map.items()
        if key in remote_map and remote_map[key] == payload
        for name in (key[1],)
    ]
    return CommandDiff(added=added, removed=removed, changed=changed, unchanged=unchanged)


class GlobalOverwriteRefusedError(RuntimeError):
    """Raised when a global sync would delete commands and ``confirm_deletions`` is False."""


async def sync_commands(
    client: DiscordClient,
    application_id: str,
    commands: list[Command],
    *,
    guild_id: str | None = None,
    dry_run: bool = False,
    confirm_deletions: bool = False,
) -> CommandDiff:
    """Bulk-overwrite commands for a guild (``guild_id``) or globally (``None``).

    Always computes and returns the diff. Performs the ``PUT`` only when not ``dry_run`` and
    the diff is non-empty. A **global** sync that would *remove* commands requires
    ``confirm_deletions=True`` (destructive operation policy).
    """
    remote = (
        await client.get_guild_commands(application_id, guild_id)
        if guild_id
        else await client.get_global_commands(application_id)
    )
    diff = diff_commands(remote, commands)
    if diff.is_empty or dry_run:
        return diff
    if guild_id is None and diff.removed and not confirm_deletions:
        msg = (
            "global sync would delete commands "
            f"{diff.removed}; re-run with confirm_deletions=True (--yes)"
        )
        raise GlobalOverwriteRefusedError(msg)

    payload = [c.to_payload() for c in commands]
    if guild_id:
        await client.put_guild_commands(application_id, guild_id, payload)
    else:
        await client.put_global_commands(application_id, payload)
    return diff
