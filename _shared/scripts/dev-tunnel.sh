#!/usr/bin/env bash
# Expose a local interactions server on a public HTTPS URL for the Developer Portal.
# Usage: _shared/scripts/dev-tunnel.sh [port]   (default 8000)
# Prefers cloudflared (quick tunnel, no account), falls back to ngrok.
# Paste "<public-url>/interactions" into General Information › Interactions Endpoint URL.
set -euo pipefail

PORT="${1:-8000}"
log() { printf '[dev-tunnel] %s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }

if command -v cloudflared >/dev/null 2>&1; then
  log "cloudflared quick tunnel → http://127.0.0.1:$PORT (Ctrl+C to stop)"
  log "look for the https://*.trycloudflare.com URL below; endpoint = <url>/interactions"
  exec cloudflared tunnel --url "http://127.0.0.1:$PORT"
elif command -v ngrok >/dev/null 2>&1; then
  log "ngrok → http://127.0.0.1:$PORT (Ctrl+C to stop); endpoint = <forwarding-url>/interactions"
  exec ngrok http "$PORT"
else
  die "install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) or ngrok (https://ngrok.com/download)"
fi
