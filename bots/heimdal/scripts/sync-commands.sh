#!/usr/bin/env bash
# Register application commands. Default target: DISCORD_DEV_GUILD_ID (instant, safe).
# Usage: sync-commands.sh [--guild ID | --global] [--dry-run] [--yes]
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$BOT_DIR" rev-parse --show-toplevel 2>/dev/null || { cd "$BOT_DIR/../.." && pwd; })"

log() { printf '[sync-commands] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

[[ -f "$BOT_DIR/.env" ]] || die "missing $BOT_DIR/.env (copy .env.example and fill it)"

if [[ " $* " == *" --global "* && " $* " != *" --dry-run "* ]]; then
  log "GLOBAL sync: commands missing locally will be DELETED on Discord (pass --yes to confirm)."
fi

cd "$BOT_DIR"
exec uv run --project "$REPO_ROOT" heimdal sync-commands "$@"
