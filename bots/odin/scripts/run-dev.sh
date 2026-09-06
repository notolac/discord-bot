#!/usr/bin/env bash
# Start the interactions server with auto-reload. Run from the repo root.
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$BOT_DIR" rev-parse --show-toplevel 2>/dev/null || { cd "$BOT_DIR/../.." && pwd; })"

log() { printf '[run-dev] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

[[ -f "$BOT_DIR/.env" ]] || die "missing $BOT_DIR/.env (copy .env.example and fill it)"

cd "$BOT_DIR"
log "starting odin from $BOT_DIR (env: .env)"
exec uv run --project "$REPO_ROOT" odin serve --reload "$@"
