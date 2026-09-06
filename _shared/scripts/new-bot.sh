#!/usr/bin/env bash
# Create a new bot folder from bots/_template and register it in the uv workspace.
# Usage: _shared/scripts/new-bot.sh <name> "<one-line purpose>"
#   <name> must be ASCII, lowercase, start with a letter: [a-z][a-z0-9_]* (e.g. thor)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || { cd "$SCRIPT_DIR/../.." && pwd; })"

log() { printf '[new-bot] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

NAME="${1:-}"
PURPOSE="${2:-}"
[[ -n "$NAME" && -n "$PURPOSE" ]] || die "usage: new-bot.sh <name> \"<purpose>\""
[[ "$NAME" =~ ^[a-z][a-z0-9_]*$ ]] || die "name must match [a-z][a-z0-9_]* (got: $NAME)"

TEMPLATE="$REPO_ROOT/bots/_template"
TARGET="$REPO_ROOT/bots/$NAME"
[[ -d "$TEMPLATE" ]] || die "template not found: $TEMPLATE"
[[ ! -e "$TARGET" ]] || die "already exists: $TARGET"

PKG="$NAME"                         # python package: snake_case
DIST="${NAME//_/-}"                 # distribution / CLI name: kebab-case
TITLE="$(printf '%s' "$NAME" | sed -E 's/_/ /g; s/\b(.)/\u\1/g')"

log "creating $TARGET (package=$PKG, cli=$DIST, title=\"$TITLE\")"
cp -R "$TEMPLATE" "$TARGET"
mv "$TARGET/src/bot_template" "$TARGET/src/$PKG"

# Rename identifiers inside files (order matters: longest / most specific first).
find "$TARGET" -type f \( -name '*.py' -o -name '*.toml' -o -name '*.md' -o -name '*.sh' -o -name '*.json' -o -name '.env.example' \) -print0 \
  | xargs -0 sed -i \
      -e "s/Bot Template — replace with the bot's purpose/$TITLE — $PURPOSE/g" \
      -e "s/bot_template/$PKG/g" \
      -e "s/bot-template/$DIST/g" \
      -e "s/Bot Template/$TITLE/g"

# Register in the workspace root so `uv sync` picks it up.
ROOT_TOML="$REPO_ROOT/pyproject.toml"
if ! grep -q "^    \"$DIST\",$" "$ROOT_TOML"; then
  sed -i "/^dependencies = \[$/a\\    \"$DIST\"," "$ROOT_TOML"
  sed -i "/^\[tool.uv.sources\]$/a\\$DIST = { workspace = true }" "$ROOT_TOML"
fi
if ! grep -q "\"bots/$NAME/tests\"" "$ROOT_TOML"; then
  sed -i "s|^testpaths = \[\(.*\)\]$|testpaths = [\1, \"bots/$NAME/tests\"]|" "$ROOT_TOML"
fi

chmod +x "$TARGET"/scripts/*.sh
log "syncing workspace"
(cd "$REPO_ROOT" && uv sync)

log "done. Next steps:"
cat >&2 <<EOF
  1. cp bots/$NAME/.env.example bots/$NAME/.env   # fill from the Developer Portal
  2. edit bots/$NAME/README.md (purpose, commands, permissions)
  3. bash bots/$NAME/scripts/smoke-test.sh
  4. add the bot to bots/README.md
EOF
