# Bots

One folder per bot; each is a separate Discord Application (own ID, key and token) and a uv
workspace member depending on `discord-core`.

| Bot | Purpose | CLI | Default port | Status |
|-----|---------|-----|--------------|--------|
| [heimdal](heimdal/README.md) | Onboarding: `/welcome` + rules button, `/roles`, `/introduce` modal | `uv run heimdal …` | 8000 | Base implemented; not deployed |
| [odin](odin/README.md) | Moderation: `/warn`, `/timeout`, `/purge` (confirm), *Report message*, *View history*; JSONL audit log | `uv run odin …` | 8001 | Base implemented; not deployed |
| [_template](_template/README.md) | Scaffold with `/ping` | — | — | Source for `new-bot.sh`; excluded from the workspace |

## Adding a bot

```bash
bash _shared/scripts/new-bot.sh <name> "<purpose>"    # name: [a-z][a-z0-9_]*
```

Then follow [`docs/developer-portal.md`](../docs/developer-portal.md), fill the README sections
(Purpose · Commands · Permissions · Variables · Decisions · Pending) and add a row above.

## Shared CLI (every bot)

| Subcommand | Effect |
|------------|--------|
| `serve [--reload] [--host] [--port]` | Run the interactions HTTP server |
| `sync-commands [--guild ID\|--global] [--dry-run] [--yes]` | Diff and bulk-register commands |
| `list-commands` | Print declared command payloads (JSON) and warn on handler mismatches |
| `smoke` | Offline endpoint self-test with a throwaway key pair |
