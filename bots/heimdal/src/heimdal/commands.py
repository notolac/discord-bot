"""Heimdal application commands (English defaults, ``es-ES`` localizations)."""

from discord_core.commands import Command, Option
from discord_core.interactions import OptionType, Permissions

COMMANDS: list[Command] = [
    Command(
        name="welcome",
        description="Send the welcome message with the rules-acceptance button",
        name_localizations={"es-ES": "bienvenida"},
        description_localizations={
            "es-ES": "Envía el mensaje de bienvenida con el botón de reglas"
        },
        options=[
            Option(
                name="user",
                description="Member to welcome (default: yourself)",
                type=OptionType.USER,
                name_localizations={"es-ES": "usuario"},
                description_localizations={
                    "es-ES": "Miembro a dar la bienvenida (por defecto: tú)"
                },
            ),
        ],
        default_member_permissions=Permissions.MANAGE_GUILD,
    ),
    Command(
        name="roles",
        description="Pick your interest roles",
        description_localizations={"es-ES": "Elige tus roles de interés"},
    ),
    Command(
        name="introduce",
        description="Introduce yourself to the community",
        name_localizations={"es-ES": "presentarme"},
        description_localizations={"es-ES": "Preséntate a la comunidad"},
    ),
]
