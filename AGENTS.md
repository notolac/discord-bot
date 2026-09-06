# AGENTS — LLM only

**Last modified:** 2026-09-06 (foundations: `discord_core`, Heimdal, Odin, `discord-docs` skill)

Human intro + repo map (Spanish): [README.md](README.md).
Roadmap / phases: [PLAN-IMPLEMENTACION.md](PLAN-IMPLEMENTACION.md).
Architecture: [docs/architecture.md](docs/architecture.md).
Developer Portal checklist: [docs/developer-portal.md](docs/developer-portal.md).
Open work: [tareas/README.md](tareas/README.md).
Script catalog: [_shared/scripts/GUIDE.md](_shared/scripts/GUIDE.md).
Official Discord docs (skill): [.cursor/skills/discord-docs/SKILL.md](.cursor/skills/discord-docs/SKILL.md).

---

## RULES (this file)

- **RULE:** Show **last modified** date at top; bump when you change this file.
- **RULE:** Write **English** only here.
- **RULE:** **English-only code**: identifiers, comments, docstrings, tests, log/exception messages, CLI help, env var names, JSONL keys, commit messages, and every technical doc (`AGENTS.md`, `docs/`, bot READMEs, `tareas/`, skills, rules). Only the root `README.md` is Spanish (human entry point). Non-English code is a **blocker**, not a nit.
- **RULE:** Discord-facing strings (command names/descriptions, buttons, modal titles, messages) are authored in **`en-US`** and localized through `name_localizations` / `description_localizations` and the bot's `i18n/<locale>.json` (`es-ES` shipped). No Spanish literals inline in handlers.
- **RULE:** New Python → **uv** only, **Python 3.14** (`requires-python = "==3.14.*"`), direct deps pinned **`==`**, one `uv.lock` at repo root (commit it). No `pip install`, no version ranges.
- **RULE:** **Never** commit `.env`, tokens, or real app public keys. `.env.example` holds placeholders only. Observed gitignored: `.env*`, `**/logs/*`, `**/reports/*`, `docs/discord/`.
- **RULE:** **Destructive Discord ops need explicit user yes** before running: `/purge`, ban/kick, **global** command sync (bulk `PUT` deletes commands not in the list — CLI refuses without `--yes`), deleting commands, changing bot permissions/intents/endpoint URL in the Portal.
- **RULE:** Register commands to the **dev guild** first (`DISCORD_DEV_GUILD_ID`, instant). Global only when the user asks.
- **RULE:** One bot ↔ one Application ID ↔ one token. Never share tokens between bots.
- **RULE:** Interaction handlers answer within **3 s** or are declared `defer=True` (router ACKs, runs later, edits original). Token lives 15 min.
- **RULE:** Before answering Discord API questions or adding API calls, use the **`discord-docs` skill**: local mirror `docs/discord/` → fetch script → web last. Cite the page. Do not invent endpoints, enums, or limits.
- **RULE:** Logs → the bot's `logs/`; script/audit outputs → the bot's `reports/`; both gitignored except `.gitkeep` / `README.md`.
- **RULE:** Do not invent paths or commands. Prefer links to source-of-truth docs. Match the language of the file you edit.

---

## What this repo is (real)

Monorepo of Discord bots built on the **HTTP interactions** model (FastAPI endpoint + Ed25519
verification), sharing one thin library. Python 3.14, uv workspace, pytest, ruff. No CI yet.

| Tree | Role |
|------|------|
| [`_shared/discord_core/`](_shared/discord_core/README.md) | Shared library: security, models, response builders, command sync, router, HTTP client, app factory, settings, logging, i18n, CLI |
| [`_shared/scripts/`](_shared/scripts/GUIDE.md) | Cross-bot scripts: `new-bot.sh`, `dev-tunnel.sh` |
| [`bots/<name>/`](bots/README.md) | One bot per folder (`heimdal` onboarding, `odin` moderation, `_template`) |
| [`docs/`](docs/) | Architecture, Developer Portal checklist, `docs/discord/` mirror (generated) |
| [`.cursor/skills/discord-docs/`](.cursor/skills/discord-docs/SKILL.md) | Official docs knowledge base + mirror script |
| [`tareas/`](tareas/README.md) | Open work board (one `.md` per task) |

Root `pyproject.toml` is a **virtual** workspace (`package = false`) that lists every member as a
dependency so `uv sync` installs everything. `bots/_template` is excluded from the workspace.

---

## Source of truth map (use this first)

| Need | Read |
|------|------|
| Why HTTP interactions, when Gateway | [docs/architecture.md](docs/architecture.md) |
| Create app, keys, intents, install link, endpoint URL | [docs/developer-portal.md](docs/developer-portal.md) |
| Library modules and responsibilities | [_shared/discord_core/README.md](_shared/discord_core/README.md) |
| Bot inventory + status | [bots/README.md](bots/README.md) |
| Heimdal commands / permissions / decisions | [bots/heimdal/README.md](bots/heimdal/README.md) · [design](bots/heimdal/docs/design.md) |
| Odin commands / audit log format / decisions | [bots/odin/README.md](bots/odin/README.md) · [design](bots/odin/docs/design.md) |
| New bot procedure | [bots/_template/README.md](bots/_template/README.md) · `_shared/scripts/new-bot.sh` |
| Official Discord facts (enums, limits, endpoints) | skill [SKILL.md](.cursor/skills/discord-docs/SKILL.md) · index [index.md](.cursor/skills/discord-docs/index.md) · mirror `docs/discord/` |
| Pending work | [tareas/README.md](tareas/README.md) |
| Plan and phases | [PLAN-IMPLEMENTACION.md](PLAN-IMPLEMENTACION.md) |

---

## Layout conventions

### Per bot (`bots/<name>/`)

`README.md` · `pyproject.toml` · `.env.example` · `src/<name>/` (`commands.py`, `handlers.py`,
`settings.py`, `__main__.py`, optional `services/`, `gateway/`) · `i18n/` (`en-US.json`, `es-ES.json`)
· `scripts/` (`run-dev.sh`, `sync-commands.sh`, `smoke-test.sh`, `README.md`) · `tests/` · `docs/` ·
`logs/.gitkeep` · `reports/.gitkeep` + `README.md`.

Folder and package names are ASCII `snake_case`; CLI/distribution names are kebab-case
(`bot_template` / `bot-template`). Accented names ("Odín") appear only in prose.

### Handlers

- `commands.py` declares `COMMANDS: list[Command]`; `handlers.py` exposes `router: Router`.
- `@router.command("<name>")` name must equal the declared command name (CLI warns on mismatch;
  tests assert equality).
- Components: `@router.component("<prefix_>")`, longest prefix wins; encode state in `custom_id`
  (≤ 100 chars) — the bots are stateless.
- Return payloads from `discord_core.responses`; never hand-build dicts in handlers.
- Discord API calls go through `ctx.client` (`DiscordClient`); catch `DiscordAPIError` and reply
  ephemerally on failure.
- Text via `ctx.t("key", interaction, **kwargs)`; keys live in `i18n/en-US.json` (+ `es-ES.json`).

### Tests

- pytest with `asyncio_mode = "auto"`; fixtures per bot in `tests/conftest.py`. Do **not**
  `from conftest import …` (module name collides across test dirs) — expose factories as fixtures.
- Discord API is mocked with `httpx.MockTransport`; no network in tests.
- Every bot has `test_every_declared_command_has_a_handler`.

---

## Essential commands (run from repo root)

```bash
uv sync                                   # whole workspace (members listed in root pyproject)
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
uv run heimdal smoke  |  bash bots/heimdal/scripts/smoke-test.sh      # offline endpoint self-test
uv run heimdal list-commands                                          # payloads as JSON
bash bots/heimdal/scripts/sync-commands.sh [--dry-run] [--global --yes]
bash bots/heimdal/scripts/run-dev.sh                                  # uvicorn --reload (needs .env)
bash _shared/scripts/dev-tunnel.sh 8000                               # cloudflared/ngrok public URL
bash _shared/scripts/new-bot.sh thor "Events bot"                     # scaffold + register in workspace
python .cursor/skills/discord-docs/scripts/fetch_discord_docs.py [--all|--check|<slug>]
```

Same commands with `odin` (default port 8001 in its `.env.example`).

---

## Build / test / lint reality

- No CI (task: [tareas/ci.md](tareas/ci.md)). Local gate = ruff + pytest + smoke.
- `ruff` config at root: `I N D UP B` + google docstrings; tests skip `D`; `bots/_template` is
  excluded from the workspace and from ruff's default paths (lint it explicitly).
- `uv sync` may need `UV_LINK_MODE=copy` on filesystems without hardlinks (observed 2026-09-06).
- `fastapi.testclient` emits a `StarletteDeprecationWarning` about `httpx` — harmless for now.

---

## High-risk gotchas

- Global command `PUT` **replaces** the whole set; the CLI raises `GlobalOverwriteRefusedError`
  unless `--yes`. Guild sync never deletes globals and vice versa.
- Enabling **Gateway** for an app disables its HTTP Interactions Endpoint (mutually exclusive per
  app). Decide per bot; document in its README.
- Discord validates the endpoint when saved and sends **invalid signatures on purpose**; a 200
  there gets the URL removed. Never bypass `verify_signature`.
- Components v2 (`IS_COMPONENTS_V2`) messages cannot carry `content`/`embeds`
  (`responses.message(... components_v2=True)` raises if you try).
- `DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE` accepts only the `EPHEMERAL` flag.
- Bulk delete: 2–100 ids, none older than 14 days; single id → plain `DELETE` (client handles it).
- `default_member_permissions` is a **string**; `"0"` hides the command from everyone but admins.
- `bots/_template` renames rely on the literal tokens `bot_template` / `bot-template` /
  `Bot Template`; keep them intact inside the template.

---

## Destructive operations policy

Need **explicit user yes** before:

- `/purge` runs against a real channel; `/ban`, `/kick` (when implemented).
- Global command sync that removes commands; deleting commands.
- Rotating tokens / public keys, changing intents, install contexts or the Interactions Endpoint URL.
- Deleting `reports/` data (contains user IDs; retention in each `reports/README.md`).

CLI flags (`--yes`) are **not** a substitute for user approval.

---

## If you update this file later

- Keep English. Stay concise; prefer links over long tables. Bump the date line.
- Only document observed facts (versions, commands, behaviour verified in this repo).
