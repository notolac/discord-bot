"""Bot-specific settings (extend the shared base). Prefix new variables with the bot name."""

from discord_core import DiscordSettings


class Settings(DiscordSettings):
    """Environment configuration for this bot."""

    # Example:
    # bot_template_welcome_channel_id: str | None = None
