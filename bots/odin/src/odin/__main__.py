"""CLI entry point: ``uv run odin <serve|sync-commands|list-commands|smoke>``."""

import sys

from discord_core import run_cli
from odin import BOT_NAME, BOT_ROOT
from odin.commands import COMMANDS
from odin.handlers import router
from odin.settings import Settings


def main() -> None:
    """Run the shared CLI for Odin."""
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
