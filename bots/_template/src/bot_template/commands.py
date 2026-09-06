"""Application command declarations (what gets registered with Discord)."""

from discord_core.commands import Command

COMMANDS: list[Command] = [
    Command(
        name="ping",
        description="Check that the bot is alive",
        description_localizations={"es-ES": "Comprueba que el bot está activo"},
    ),
]
