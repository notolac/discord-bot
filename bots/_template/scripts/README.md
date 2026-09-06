# Scripts — Bot Template

Run from the **repo root**. All wrap `uv run bot-template …` (shared CLI in `discord_core.cli`).

| Script | What it does | When |
|--------|--------------|------|
| `run-dev.sh` | Loads `.env`, starts uvicorn with reload | Local development |
| `sync-commands.sh [--global] [--dry-run] [--yes]` | Diff + bulk `PUT` of commands to `DISCORD_DEV_GUILD_ID` (default) or `--guild` / globally | After editing `commands.py` |
| `smoke-test.sh` | Offline self-test: signed PING → PONG, unsigned → 401, unknown command → ephemeral | Before pushing / after touching `discord_core` |

Global sync deletes commands that are no longer declared; `--yes` is required in that case
(see `AGENTS.md` › Destructive operations).
