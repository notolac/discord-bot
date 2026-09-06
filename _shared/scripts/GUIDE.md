# Scripts guide

All scripts are Bash (`set -euo pipefail`, `log()`/`die()`), run from the **repo root**, and never
need `sudo`. Per-bot scripts live in `bots/<bot>/scripts/` (documented in each `scripts/README.md`).

## Repo-level (`_shared/scripts/`)

| Script | Purpose | When to run | Side effects |
|--------|---------|-------------|--------------|
| `new-bot.sh <name> "<purpose>"` | Copies `bots/_template` → `bots/<name>`, renames `bot_template`/`bot-template`/`Bot Template`, registers the member in the root `pyproject.toml` (dependencies, sources, `testpaths`) and runs `uv sync` | Creating a bot | Edits root `pyproject.toml`, creates files, updates `uv.lock` |
| `dev-tunnel.sh [port]` | Public HTTPS URL to a local server via `cloudflared` (quick tunnel) or `ngrok` | Testing the Interactions Endpoint URL from the Portal | None (foreground process) |

## Per-bot (`bots/<bot>/scripts/`)

| Script | Wraps | Notes |
|--------|-------|-------|
| `run-dev.sh` | `uv run <bot> serve --reload` | Requires `bots/<bot>/.env` |
| `sync-commands.sh [--guild ID\|--global] [--dry-run] [--yes]` | `uv run <bot> sync-commands` | Default target `DISCORD_DEV_GUILD_ID`; global deletions need `--yes` |
| `smoke-test.sh` | `uv run <bot> smoke` | Offline: PING→PONG, unsigned→401, unknown command→ephemeral |

## Skill script (`.cursor/skills/discord-docs/scripts/`)

| Script | Purpose |
|--------|---------|
| `fetch_discord_docs.py [--all\|--check\|<slug>…]` | Mirrors official docs (`.md`) into `docs/discord/`; stdlib only |

## Conventions

- Syntax check before commit: `bash -n <script>`.
- Destructive actions are gated (`--yes`) **and** still need the user's explicit approval.
- Output for humans goes to stderr via `log()`; machine output (JSON) to stdout.
