#!/usr/bin/env bash
# Offline self-test of the interactions endpoint (no network, no real token).
set -euo pipefail

BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(git -C "$BOT_DIR" rev-parse --show-toplevel 2>/dev/null || { cd "$BOT_DIR/../.." && pwd; })"

cd "$BOT_DIR"
exec uv run --project "$REPO_ROOT" bot-template smoke
