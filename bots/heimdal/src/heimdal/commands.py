"""Heimdal application commands (English defaults, ``es-ES`` localizations)."""

from discord_core.commands import Choice, Command, Option
from discord_core.interactions import OptionType, Permissions

COMMANDS: list[Command] = [
    Command(
        name="welcome",
        description="Post the onboarding card (public, or targeted if a user is given)",
        name_localizations={"es-ES": "bienvenida"},
        description_localizations={
            "es-ES": "Publica la tarjeta de bienvenida (pública, o dirigida si hay usuario)"
        },
        options=[
            Option(
                name="user",
                description="Member to mention (omit for a persistent public card)",
                type=OptionType.USER,
                name_localizations={"es-ES": "usuario"},
                description_localizations={
                    "es-ES": "Miembro a mencionar (omítelo para una tarjeta pública)"
                },
            ),
        ],
        default_member_permissions=Permissions.MANAGE_GUILD,
    ),
    Command(
        name="request-role",
        description="Request a claimed role (staff must approve)",
        name_localizations={"es-ES": "solicitar-rol"},
        description_localizations={"es-ES": "Solicita un rol reclamado (el staff debe aprobarlo)"},
        options=[
            Option(
                name="role",
                description="Which claimed role to request",
                type=OptionType.STRING,
                required=True,
                choices=[
                    Choice(
                        "Organizer",
                        "organizer",
                        name_localizations={"es-ES": "Organizador"},
                    ),
                    Choice(
                        "Speaker",
                        "speaker",
                        name_localizations={"es-ES": "Ponente"},
                    ),
                    Choice(
                        "Startups",
                        "startups",
                        name_localizations={"es-ES": "Startups"},
                    ),
                    Choice(
                        "Enterprises",
                        "enterprises",
                        name_localizations={"es-ES": "Enterprises"},
                    ),
                ],
                name_localizations={"es-ES": "rol"},
                description_localizations={"es-ES": "Qué rol reclamado solicitar"},
            ),
        ],
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
