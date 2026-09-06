"""Enums and models for the Interaction payload.

Values are taken verbatim from the official docs:
https://docs.discord.com/developers/interactions/receiving-and-responding
https://docs.discord.com/developers/interactions/application-commands
https://docs.discord.com/developers/components/reference
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- enums


class InteractionType(IntEnum):
    """Incoming interaction ``type``."""

    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class CallbackType(IntEnum):
    """Interaction response ``type`` (interaction callback type)."""

    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9
    LAUNCH_ACTIVITY = 12


class ContextType(IntEnum):
    """Interaction context where a command can be used / was triggered."""

    GUILD = 0
    BOT_DM = 1
    PRIVATE_CHANNEL = 2


class IntegrationType(IntEnum):
    """Installation context of the app."""

    GUILD_INSTALL = 0
    USER_INSTALL = 1


class CommandType(IntEnum):
    """Application command ``type``."""

    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3
    PRIMARY_ENTRY_POINT = 4


class OptionType(IntEnum):
    """Application command option ``type``."""

    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


class ComponentType(IntEnum):
    """Message / modal component ``type`` (subset used by this repo)."""

    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8
    SECTION = 9
    TEXT_DISPLAY = 10
    THUMBNAIL = 11
    MEDIA_GALLERY = 12
    FILE = 13
    SEPARATOR = 14
    CONTAINER = 17
    LABEL = 18


class ButtonStyle(IntEnum):
    """Button ``style``."""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


class TextInputStyle(IntEnum):
    """Text input ``style``."""

    SHORT = 1
    PARAGRAPH = 2


class MessageFlags(IntFlag):
    """Message flags allowed on interaction responses."""

    SUPPRESS_EMBEDS = 1 << 2
    EPHEMERAL = 1 << 6
    SUPPRESS_NOTIFICATIONS = 1 << 12
    IS_COMPONENTS_V2 = 1 << 15


class Permissions(IntFlag):
    """Subset of permission bits used for ``default_member_permissions``."""

    KICK_MEMBERS = 1 << 1
    BAN_MEMBERS = 1 << 2
    ADMINISTRATOR = 1 << 3
    MANAGE_GUILD = 1 << 5
    MANAGE_MESSAGES = 1 << 13
    READ_MESSAGE_HISTORY = 1 << 16
    MANAGE_ROLES = 1 << 28
    MODERATE_MEMBERS = 1 << 40


# -------------------------------------------------------------------------- models


class _Model(BaseModel):
    """Base model: tolerate unknown fields so new API fields never break parsing."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class User(_Model):
    """Discord user (partial)."""

    id: str
    username: str = ""
    global_name: str | None = None
    bot: bool = False

    @property
    def display_name(self) -> str:
        """Best human-readable name available."""
        return self.global_name or self.username or self.id


class Member(_Model):
    """Guild member (partial). ``user`` is absent inside ``resolved.members``."""

    user: User | None = None
    nick: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: str | None = None


class PartialMessage(_Model):
    """Message as it appears in ``resolved.messages`` or ``interaction.message``."""

    id: str
    channel_id: str | None = None
    content: str = ""
    author: User | None = None


class ResolvedData(_Model):
    """Resolved users, members, roles, channels, messages and attachments."""

    users: dict[str, User] = Field(default_factory=dict)
    members: dict[str, Member] = Field(default_factory=dict)
    roles: dict[str, dict[str, Any]] = Field(default_factory=dict)
    channels: dict[str, dict[str, Any]] = Field(default_factory=dict)
    messages: dict[str, PartialMessage] = Field(default_factory=dict)
    attachments: dict[str, dict[str, Any]] = Field(default_factory=dict)


class InteractionDataOption(_Model):
    """One option of a command invocation; may nest for subcommands/groups."""

    name: str
    type: int
    value: str | int | float | bool | None = None
    options: list[InteractionDataOption] = Field(default_factory=list)
    focused: bool = False


class SubmittedComponent(_Model):
    """Component value submitted through a modal (flattened by ``Interaction.modal_values``)."""

    type: int
    custom_id: str | None = None
    value: str | None = None
    values: list[str] = Field(default_factory=list)
    component: SubmittedComponent | None = None
    components: list[SubmittedComponent] = Field(default_factory=list)


class InteractionData(_Model):
    """Union-ish ``data`` payload; fields depend on the interaction type."""

    # APPLICATION_COMMAND / AUTOCOMPLETE
    id: str | None = None
    name: str | None = None
    type: int | None = None
    options: list[InteractionDataOption] = Field(default_factory=list)
    target_id: str | None = None
    guild_id: str | None = None
    # MESSAGE_COMPONENT / MODAL_SUBMIT
    custom_id: str | None = None
    component_type: int | None = None
    values: list[str] = Field(default_factory=list)
    components: list[SubmittedComponent] = Field(default_factory=list)
    # shared
    resolved: ResolvedData = Field(default_factory=ResolvedData)


class Interaction(_Model):
    """Incoming interaction object."""

    id: str
    application_id: str
    type: InteractionType
    token: str
    version: int = 1
    data: InteractionData | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    member: Member | None = None
    user: User | None = None
    message: PartialMessage | None = None
    app_permissions: str | None = None
    locale: str | None = None
    guild_locale: str | None = None
    context: ContextType | None = None
    authorizing_integration_owners: dict[str, str] = Field(default_factory=dict)

    # ------------------------------------------------------------------ helpers

    @property
    def invoking_user(self) -> User:
        """User who triggered the interaction (``member.user`` in guilds, ``user`` in DMs)."""
        if self.member is not None and self.member.user is not None:
            return self.member.user
        if self.user is not None:
            return self.user
        msg = "interaction has neither member.user nor user"
        raise ValueError(msg)

    @property
    def command_name(self) -> str | None:
        """Top-level command name, if this is a command interaction."""
        return self.data.name if self.data else None

    @property
    def custom_id(self) -> str | None:
        """``custom_id`` for component / modal interactions."""
        return self.data.custom_id if self.data else None

    def subcommand_path(self) -> list[str]:
        """Return ``[group, subcommand]`` (or ``[subcommand]``) names, empty for plain commands."""
        path: list[str] = []
        options = self.data.options if self.data else []
        while options:
            first = options[0]
            if first.type in (OptionType.SUB_COMMAND, OptionType.SUB_COMMAND_GROUP):
                path.append(first.name)
                options = first.options
            else:
                break
        return path

    def leaf_options(self) -> dict[str, str | int | float | bool | None]:
        """Flatten the innermost option values (descending into subcommands) into a dict."""
        options = self.data.options if self.data else []
        while options and options[0].type in (OptionType.SUB_COMMAND, OptionType.SUB_COMMAND_GROUP):
            options = options[0].options
        return {opt.name: opt.value for opt in options}

    def option(self, name: str, default: Any = None) -> Any:
        """Shortcut for ``leaf_options().get(name, default)``."""
        return self.leaf_options().get(name, default)

    def focused_option(self) -> InteractionDataOption | None:
        """Option currently being autocompleted, if any."""
        options = self.data.options if self.data else []
        stack = list(options)
        while stack:
            opt = stack.pop()
            if opt.focused:
                return opt
            stack.extend(opt.options)
        return None

    def modal_values(self) -> dict[str, str | list[str]]:
        """Flatten modal submit components into ``{custom_id: value | values}``."""
        result: dict[str, str | list[str]] = {}
        stack: list[SubmittedComponent] = list(self.data.components) if self.data else []
        while stack:
            comp = stack.pop()
            if comp.custom_id:
                result[comp.custom_id] = comp.values if comp.values else (comp.value or "")
            if comp.component is not None:
                stack.append(comp.component)
            stack.extend(comp.components)
        return result

    def resolved_user(self, user_id: str) -> User | None:
        """Resolved user by id (from options or ``target_id``)."""
        return self.data.resolved.users.get(user_id) if self.data else None

    def resolved_message(self, message_id: str) -> PartialMessage | None:
        """Resolved message by id (message context-menu commands)."""
        return self.data.resolved.messages.get(message_id) if self.data else None
