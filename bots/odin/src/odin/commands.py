"""Odin application commands (English defaults, ``es-ES`` localizations)."""

from discord_core.commands import Command, Option
from discord_core.interactions import CommandType, OptionType, Permissions

MAX_TIMEOUT_MINUTES = 40_320  # 28 days, Discord's maximum
MAX_PURGE = 100  # bulk-delete limit per request

COMMANDS: list[Command] = [
    Command(
        name="warn",
        description="Warn a member and record it",
        name_localizations={"es-ES": "avisar"},
        description_localizations={"es-ES": "Avisa a un miembro y deja constancia"},
        default_member_permissions=Permissions.MODERATE_MEMBERS,
        options=[
            Option(
                "user",
                "Member to warn",
                type=OptionType.USER,
                required=True,
                name_localizations={"es-ES": "usuario"},
                description_localizations={"es-ES": "Miembro a avisar"},
            ),
            Option(
                "reason",
                "Why",
                required=True,
                max_length=500,
                name_localizations={"es-ES": "motivo"},
                description_localizations={"es-ES": "Motivo"},
            ),
        ],
    ),
    Command(
        name="timeout",
        description="Time a member out for a number of minutes",
        name_localizations={"es-ES": "silenciar"},
        description_localizations={"es-ES": "Silencia a un miembro durante unos minutos"},
        default_member_permissions=Permissions.MODERATE_MEMBERS,
        options=[
            Option(
                "user",
                "Member to time out",
                type=OptionType.USER,
                required=True,
                name_localizations={"es-ES": "usuario"},
                description_localizations={"es-ES": "Miembro a silenciar"},
            ),
            Option(
                "minutes",
                "Duration in minutes (1–40320)",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
                max_value=MAX_TIMEOUT_MINUTES,
                name_localizations={"es-ES": "minutos"},
                description_localizations={"es-ES": "Duración en minutos (1–40320)"},
            ),
            Option(
                "reason",
                "Why",
                max_length=500,
                name_localizations={"es-ES": "motivo"},
                description_localizations={"es-ES": "Motivo"},
            ),
        ],
    ),
    Command(
        name="purge",
        description="Delete the last N messages in this channel (asks for confirmation)",
        name_localizations={"es-ES": "limpiar"},
        description_localizations={
            "es-ES": "Borra los últimos N mensajes del canal (pide confirmación)"
        },
        default_member_permissions=Permissions.MANAGE_MESSAGES,
        options=[
            Option(
                "count",
                "How many messages (1–100)",
                type=OptionType.INTEGER,
                required=True,
                min_value=1,
                max_value=MAX_PURGE,
                name_localizations={"es-ES": "cantidad"},
                description_localizations={"es-ES": "Cuántos mensajes (1–100)"},
            ),
        ],
    ),
    Command(
        name="Report message",
        type=CommandType.MESSAGE,
        name_localizations={"es-ES": "Reportar mensaje"},
    ),
    Command(
        name="View history",
        type=CommandType.USER,
        name_localizations={"es-ES": "Ver historial"},
        default_member_permissions=Permissions.MODERATE_MEMBERS,
    ),
]
