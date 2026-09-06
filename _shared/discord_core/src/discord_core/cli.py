"""Shared command-line entry point for bots.

Subcommands:
* ``serve``          — run the interactions HTTP server (uvicorn).
* ``sync-commands``  — diff + bulk ``PUT`` commands to ``DISCORD_DEV_GUILD_ID`` (default)
  or ``--guild`` / globally. ``DISCORD_PROD_GUILD_ID`` is never the implicit target.
* ``list-commands``  — print the local command payloads as JSON.
* ``smoke``          — offline self-test: signed PING → PONG and an unknown command → ephemeral.

Every bot's ``__main__`` calls :func:`run_cli`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import structlog

from discord_core.app import create_app
from discord_core.commands import Command, GlobalOverwriteRefusedError, sync_commands
from discord_core.http import DiscordClient
from discord_core.i18n import Localizer
from discord_core.logging import configure_logging
from discord_core.router import Router
from discord_core.security import generate_keypair, sign_payload
from discord_core.settings import DiscordSettings


def run_cli(
    *,
    bot_name: str,
    router: Router,
    commands: list[Command],
    settings_cls: type[DiscordSettings] = DiscordSettings,
    bot_root: Path | None = None,
    argv: list[str] | None = None,
) -> int:
    """Parse ``argv`` and run the requested subcommand. Returns the process exit code."""
    parser = argparse.ArgumentParser(prog=bot_name, description=f"{bot_name} Discord bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="run the interactions HTTP server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true", help="dev auto-reload")

    sync = sub.add_parser("sync-commands", help="register commands (guild by default)")
    scope = sync.add_mutually_exclusive_group()
    scope.add_argument(
        "--guild",
        metavar="GUILD_ID",
        help="target guild (default: DISCORD_DEV_GUILD_ID; prod: pass DISCORD_PROD_GUILD_ID)",
    )
    scope.add_argument(
        "--global", dest="global_scope", action="store_true", help="register globally"
    )
    sync.add_argument("--dry-run", action="store_true", help="only print the diff")
    sync.add_argument("--yes", action="store_true", help="confirm deletions on a global sync")

    sub.add_parser("list-commands", help="print local command payloads as JSON")
    sub.add_parser("smoke", help="offline self-test of the interactions endpoint")

    args = parser.parse_args(argv)

    if args.cmd == "list-commands":
        _check_router_coverage(router, commands)
        print(json.dumps([c.to_payload() for c in commands], indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "smoke":
        return _smoke(bot_name, router, bot_root)

    settings = settings_cls()  # type: ignore[call-arg]  # values come from env/.env
    if bot_root is not None:
        if settings.log_dir is None:
            settings.log_dir = bot_root / "logs"
        if settings.i18n_dir is None:
            settings.i18n_dir = bot_root / "i18n"
    settings.bot_name = bot_name
    configure_logging(settings.log_level, log_dir=settings.log_dir, name=bot_name)
    log = structlog.get_logger(bot_name)

    if args.cmd == "serve":
        import uvicorn

        app = create_app(settings, router)
        uvicorn.run(
            app,
            host=args.host or settings.host,
            port=args.port or settings.port,
            reload=args.reload,
            log_config=None,
        )
        return 0

    if args.cmd == "sync-commands":
        _check_router_coverage(router, commands)
        guild_id = None if args.global_scope else (args.guild or settings.discord_dev_guild_id)
        if guild_id is None and not args.global_scope:
            log.error(
                "no_guild",
                hint="set DISCORD_DEV_GUILD_ID, pass --guild (DISCORD_PROD_GUILD_ID is never default), or use --global",
            )
            return 2
        return asyncio.run(
            _sync(settings, commands, guild_id=guild_id, dry_run=args.dry_run, confirm=args.yes)
        )

    parser.error(f"unknown command {args.cmd!r}")
    return 2


async def _sync(
    settings: DiscordSettings,
    commands: list[Command],
    *,
    guild_id: str | None,
    dry_run: bool,
    confirm: bool,
) -> int:
    log = structlog.get_logger("sync-commands")
    scope = f"guild {guild_id}" if guild_id else "GLOBAL"
    async with DiscordClient(
        settings.discord_bot_token.get_secret_value(), version=settings.bot_version
    ) as client:
        try:
            diff = await sync_commands(
                client,
                settings.discord_app_id,
                commands,
                guild_id=guild_id,
                dry_run=dry_run,
                confirm_deletions=confirm,
            )
        except GlobalOverwriteRefusedError as exc:
            log.error("global_sync_refused", reason=str(exc))
            return 3
    log.info(
        "sync_result",
        scope=scope,
        dry_run=dry_run,
        added=diff.added,
        removed=diff.removed,
        changed=diff.changed,
        unchanged=len(diff.unchanged),
    )
    print(f"[{scope}] {'DRY-RUN ' if dry_run else ''}{diff.summary()}")
    for label, names in (("+", diff.added), ("-", diff.removed), ("~", diff.changed)):
        for name in names:
            print(f"  {label} {name}")
    return 0


def _check_router_coverage(router: Router, commands: list[Command]) -> None:
    """Warn when declared commands have no handler or vice versa."""
    declared = {c.name for c in commands}
    handled = set(router.command_names)
    for name in sorted(declared - handled):
        print(f"warning: command {name!r} is declared but has no handler", file=sys.stderr)
    for name in sorted(handled - declared):
        print(f"warning: handler {name!r} has no declared command", file=sys.stderr)


def _smoke(bot_name: str, router: Router, bot_root: Path | None) -> int:
    """Run the endpoint in-process with a throwaway key pair; no network, no real token."""
    from fastapi.testclient import TestClient

    private_key, public_key = generate_keypair()
    settings = DiscordSettings(
        discord_app_id="0",
        discord_public_key=public_key,
        discord_bot_token="smoke-token",  # type: ignore[arg-type]
        bot_name=bot_name,
        i18n_dir=(bot_root / "i18n") if bot_root else None,
    )
    configure_logging("ERROR")
    app = create_app(settings, router, localizer=Localizer.from_dir(settings.i18n_dir))
    failures = 0

    def post(payload: dict[str, Any], *, signed: bool = True) -> Any:
        body = json.dumps(payload).encode()
        timestamp = str(int(time.time()))
        headers = {"Content-Type": "application/json"}
        if signed:
            headers["X-Signature-Ed25519"] = sign_payload(private_key, timestamp, body)
            headers["X-Signature-Timestamp"] = timestamp
        return client.post("/interactions", content=body, headers=headers)

    with TestClient(app) as client:
        checks = [
            ("healthz", client.get("/healthz"), 200, lambda j: j["status"] == "ok"),
            ("ping -> pong", post({"type": 1}), 200, lambda j: j == {"type": 1}),
            ("unsigned -> 401", post({"type": 1}, signed=False), 401, lambda j: True),
            (
                "unknown command -> ephemeral",
                post(
                    {
                        "id": "1",
                        "application_id": "0",
                        "type": 2,
                        "token": "t",
                        "version": 1,
                        "data": {"id": "1", "name": "__smoke__", "type": 1},
                        "user": {"id": "42", "username": "smoke"},
                    }
                ),
                200,
                lambda j: j["type"] == 4 and j["data"]["flags"] & 64,
            ),
        ]
        for name, response, status, predicate in checks:
            ok = response.status_code == status and predicate(response.json())
            failures += 0 if ok else 1
            print(f"[{'OK' if ok else 'FAIL'}] {name} ({response.status_code})")
    print(f"smoke: {len(checks) - failures}/{len(checks)} checks passed")
    return 0 if failures == 0 else 1
