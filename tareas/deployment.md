# Deployment — stable public endpoint

**Status:** open · **Area:** all bots · **Depends on:** homelab (`~/Work/Personal/home-lab`)

## Goal

Run Heimdal and Odin 24/7 behind a stable HTTPS URL so Discord's periodic endpoint validation
never fails (a failure removes the Interactions Endpoint URL).

## Scope

- [ ] `Dockerfile` per bot (multi-stage: `uv sync --frozen --no-dev`, non-root, `CMD ["uv","run","<bot>","serve","--host","0.0.0.0"]`).
- [ ] `GET /healthz` wired to the orchestrator probe.
- [ ] Secrets injected as env (`DISCORD_*`), never baked into images.
- [ ] Route: Traefik (K3s) or Cloudflare Tunnel — decide with the homelab owner; document in `docs/architecture.md`.
- [ ] Persistent volume for `reports/` (Odin) and `logs/`.
- [ ] Runbook: rotate token / re-save endpoint URL.

## Notes

`dev-tunnel.sh` (cloudflared quick tunnel / ngrok) is for development only; URLs change on restart.
