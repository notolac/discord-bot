"""CLI entry point: ``uv run bot-template <serve|sync-commands|list-commands|smoke>``."""

import sys

from bot_template import BOT_NAME, BOT_ROOT
from bot_template.commands import COMMANDS
from bot_template.handlers import router
from bot_template.settings import Settings
from discord_core import run_cli


def main() -> None:
    """Run the shared CLI for this bot."""
    sys.exit(
        run_cli(
            bot_name=BOT_NAME,
            router=router,
            commands=COMMANDS,
            settings_cls=Settings,
            bot_root=BOT_ROOT,
        )
    )


if __name__ == "__main__":
    main()
