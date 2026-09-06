"""CLI entry point: ``uv run heimdal <serve|sync-commands|list-commands|smoke>``."""

import sys

from discord_core import run_cli
from heimdal import BOT_NAME, BOT_ROOT
from heimdal.commands import COMMANDS
from heimdal.handlers import router
from heimdal.settings import Settings


def main() -> None:
    """Run the shared CLI for Heimdal."""
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
