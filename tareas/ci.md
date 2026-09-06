# CI — lint, tests, smoke

**Status:** open · **Area:** repo

- [ ] GitHub Actions workflow on push/PR: `uv sync`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`, `uv run heimdal smoke`, `uv run odin smoke`.
- [ ] Python 3.14 via `astral-sh/setup-uv` (`.python-version`).
- [ ] Fail on non-English identifiers? (optional: a simple grep for accented characters in `src/` outside `i18n/`).
- [ ] Cache uv.
