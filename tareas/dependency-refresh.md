# Dependency refresh

**Status:** open · **Area:** repo

All direct dependencies are pinned `==` (see `_shared/discord_core/pyproject.toml`, root
`[dependency-groups]`). Refresh monthly or on security advisories:

```bash
uv lock --upgrade
uv sync
uv run ruff check . && uv run pytest -q && uv run heimdal smoke && uv run odin smoke
```

- [ ] Decide cadence (monthly?) and owner.
- [ ] Watch `fastapi`/`starlette` for the `httpx` → `httpx2` TestClient migration (deprecation warning observed 2026-09-06).
- [ ] Re-run `python Skills/discord-docs/scripts/fetch_discord_docs.py --check` to spot API doc changes.
