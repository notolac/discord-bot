# Bot Template

> Template bot. Created with `_shared/scripts/new-bot.sh <name> "<purpose>"`; replace every
> placeholder section below. Folder and package names must be ASCII / `snake_case`.

## Purpose

One paragraph: what this bot does, for whom, and what it deliberately does **not** do.

## Commands

| Command | Type | Handler | Notes |
|---------|------|---------|-------|
| `/ping` | CHAT_INPUT | `handlers.ping` | Ephemeral health reply |

## Permissions / intents

- Installation context: Guild Install (default). Add User Install only if needed.
- Scopes: `bot`, `applications.commands`.
- Bot permissions: `Send Messages` (extend as needed).
- Gateway intents: none (HTTP interactions only). Document any Gateway extension here.

## Variables

Copy `.env.example` to `.env` and fill from the Developer Portal (see `docs/developer-portal.md`).

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_APP_ID` | yes | Application ID |
| `DISCORD_PUBLIC_KEY` | yes | Public key for signature verification |
| `DISCORD_BOT_TOKEN` | yes | Bot token (never commit) |
| `DISCORD_DEV_GUILD_ID` | dev | Test server; default target for `sync-commands` |
| `DISCORD_PROD_GUILD_ID` | no | Production server (same bot token). Never an implicit default — pass `--guild` |
| `PORT` | no | HTTP port (default 8000) |

## Run

```bash
uv sync
bash bots/bot_template/scripts/sync-commands.sh      # commands → dev guild
bash bots/bot_template/scripts/run-dev.sh            # uvicorn with reload
bash bots/bot_template/scripts/smoke-test.sh         # offline self-test
bash _shared/scripts/dev-tunnel.sh 8000              # public URL for the Portal
```

## Layout

```text
src/bot_template/   commands.py (declarations) · handlers.py · settings.py · __main__.py
i18n/               en-US.json (default) · es-ES.json
scripts/            run-dev.sh · sync-commands.sh · smoke-test.sh
tests/              pytest
logs/ reports/      runtime output (gitignored)
docs/               design notes
```

## Decisions

- HTTP interactions endpoint (no Gateway). Reason: …

## Pending

- [ ] …
