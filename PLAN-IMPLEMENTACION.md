# Implementation plan — `discord-bot`

**Date:** 2026-09-06 · **Status:** phases 0–6 implemented (foundations); phase 7 (deployment) open — see [`tareas/`](tareas/README.md)

Monorepo of Discord bots in **Python 3.14 + uv**, one bot per folder, with a minimal shared
library built directly on the official API. This document is the roadmap to lay down the
**foundations** of the repo; it does not yet implement the functional logic of each bot.

## 0. Official sources used (design basis)

| Page | What it contributes to the plan |
|------|---------------------------------|
| [Getting Started](https://docs.discord.com/developers/quick-start/getting-started) | Developer Portal flow → `APP_ID`, `PUBLIC_KEY`, `BOT_TOKEN`; installation contexts (`Guild Install` / `User Install`); scopes `bot` + `applications.commands`; command registration with `PUT /applications/{app_id}/commands`; public `/interactions` endpoint (tunnel in dev) |
| [Interactions Overview](https://docs.discord.com/developers/interactions/overview) | Two **mutually exclusive** ways to receive interactions: Gateway (WebSocket) or HTTP (outgoing webhook). HTTP requires: answering `PING` (`type: 1` → `{"type": 1}`) and verifying `X-Signature-Ed25519` + `X-Signature-Timestamp` (401 on failure; Discord audits with invalid signatures) |
| [Receiving and Responding](https://docs.discord.com/developers/interactions/receiving-and-responding) | `Interaction` object (`type` 1–5, `data`, `member`/`user`, `token`, `app_permissions`, `context`, `authorizing_integration_owners`); callback types (4 message, 5 deferred, 6/7 update, 8 autocomplete, 9 modal); **3 s** for the initial response, token valid **15 min**; follow-ups via `/webhooks/{app_id}/{token}` |
| [Application Commands](https://docs.discord.com/developers/interactions/application-commands) | Types `CHAT_INPUT`/`USER`/`MESSAGE`; options (subcommands, choices, autocomplete, `min/max`, `channel_types`); **guild** commands (instant, for dev) vs **global** (cached); `POST` is an upsert; limits (100 chat / 15 user / 15 message; 200 creates per guild per day); `default_member_permissions`, `integration_types`, `contexts` |
| [Reference](https://docs.discord.com/developers/reference) | Base URL `https://discord.com/api/v10`; `Authorization: Bot <token>`; mandatory `User-Agent: DiscordBot ($url, $version)`; snowflakes as strings; rate limits (RFC 6585); `50035` error format; mention/timestamp markdown; `allowed_mentions` |

Full page index (`.md` format consumable by agents): <https://docs.discord.com/llms.txt>.
Every page also exists as plain Markdown by appending `.md` to the URL
(e.g. `https://docs.discord.com/developers/interactions/overview.md`) — basis of the skill (§7).

---

## 1. Architecture decisions

### 1.1 Reception mode: HTTP Interactions first, Gateway optional

- **Common base (all bots):** HTTP endpoint `/interactions` (FastAPI + uvicorn) with Ed25519
  verification (`PyNaCl`) and `PONG`. This is the model documented by the chosen pages, needs
  no persistent connection, scales like any HTTP service and fits the homelab (Traefik /
  Cloudflare already exist in `home-lab`).
- **Gateway extension (per bot, only when needed):** `gateway/` module with `discord.py` for
  events HTTP does not deliver (e.g. `GUILD_MEMBER_ADD` for automatic onboarding on join).
  Discord requires an app to receive interactions **through one path only**; if a bot enables
  Gateway, its interactions arrive via `INTERACTION_CREATE` and the HTTP endpoint is disabled
  for that app. Documented as an explicit decision in each bot's README.
- **One Application ID per bot** (Heimdal and Odin are separate apps in the Developer Portal).

### 1.2 Shared library `discord_core` (own, thin)

Implemented on top of the official API, no large framework:

| Module | Responsibility | Doc source |
|--------|----------------|------------|
| `http.py` | Async `httpx` client: v10 base URL, `Authorization: Bot`, correct `User-Agent`, retries on 429 honoring `Retry-After` / `X-RateLimit-*`, `50035` error parsing | Reference |
| `security.py` | `verify_signature(public_key, signature, timestamp, body)` → bool | Overview |
| `interactions.py` | `pydantic` models for `Interaction`, `InteractionData`, `ResolvedData`; enums `InteractionType`, `CallbackType`, `ContextType`, `MessageFlags` (`EPHEMERAL=64`, `IS_COMPONENTS_V2=32768`) | Receiving & Responding |
| `responses.py` | Helpers: `message()`, `ephemeral()`, `deferred()`, `update_message()`, `modal()`, `autocomplete()`; follow-ups `edit_original()`, `followup()` | Receiving & Responding |
| `commands.py` | Typed command declaration (`CHAT_INPUT`/`USER`/`MESSAGE`, options, `default_member_permissions`, `integration_types`, `contexts`, `name_localizations`/`description_localizations`) + idempotent **sync**: bulk `PUT` to guild (dev) or global (prod) with a diff first | Application Commands |
| `router.py` | Dispatch by `type` → by `data.name` (commands) or `custom_id` prefix (components/modals); decorators `@command("name")`, `@component("prefix_")`, `@modal("prefix_")` | Overview |
| `app.py` | FastAPI factory: `create_app(settings, router)` → `POST /interactions` with verification, `PONG`, 3 s deadline (auto-`deferred` if the handler declares `slow=True`) | Overview |
| `settings.py` | `pydantic-settings`: `DISCORD_APP_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_BOT_TOKEN`, `DISCORD_DEV_GUILD_ID`, `LOG_LEVEL`, `PORT` | Getting Started |
| `logging.py` | `structlog` JSON → stdout + rotated file under the bot's `logs/` | — |

Each bot depends on `discord_core` through the uv workspace (`{ workspace = true }`).

### 1.3 Toolchain

- **Python `==3.14.*`** (`.python-version` at root; already available: `cpython-3.14.7`).
- **uv workspace** (`uv 0.11.x`): one `uv.lock` at root, members `bots/*` and `_shared/discord_core`.
- Direct dependencies **pinned with `==`** (same rule as `home-lab`). Current versions at
  plan date (verify when executing): `httpx 0.28.1`, `PyNaCl 1.6.2`, `fastapi 0.141.1`,
  `uvicorn 0.52.4`, `pydantic 2.13.5`, `pydantic-settings 2.15.0`, `structlog 26.1.0`,
  `discord.py 2.7.1` (optional extra), dev: `ruff 0.16.6`, `pytest 9.1.1`, `pytest-asyncio 1.4.0`;
  build: `hatchling 1.32.0`.
- Lint/format: `ruff` (config at root). Tests: `pytest` per bot and for `discord_core`.
- No CI in the base phase (same as `home-lab`); `tareas/ci.md` left as pending.

### 1.4 Language policy (strict)

- **All new code is written in English, strictly:** identifiers (modules, packages, classes,
  functions, variables, constants, enum members), **comments**, **docstrings**, type aliases,
  test names, log messages, exception messages, CLI flags/help text, script names, env var
  names, JSON/JSONL keys in `reports/`, and commit messages.
- **Discord-facing strings** (command names, descriptions, choices, button labels, modal
  titles, message templates) are authored in **English (`en-US`) as the default** and
  localized to Spanish through `name_localizations` / `description_localizations` and a
  per-bot `i18n/` string table (`es-ES` first). No Spanish literals inline in handlers.
- **Docs:** `AGENTS.md`, `.cursor/rules/*.mdc`, the `discord-docs` skill, `docs/*.md`, bot
  README files, the root `README.md`, and `tareas/*.md` are written in **English**. Discord
  localization data remains intentionally language-specific.
- Enforced by: `ruff` (naming rules `N*`), a review checklist item in `AGENTS.md`, and a
  `.cursor/rules/discord-bot.mdc` always-on reminder. Non-English code found in a PR is a
  blocker, not a nit.

---

## 2. Target repository structure

```text
discord-bot/
├── README.md                     ← human-facing repository entry point
├── AGENTS.md                     ← LLM, English (adapted from home-lab)
├── PLAN-IMPLEMENTACION.md        ← this document
├── LICENSE
├── .gitignore
├── .python-version               ← 3.14
├── pyproject.toml                ← uv workspace root + ruff + pytest
├── uv.lock
├── .cursor/
│   └── rules/
│       └── discord-bot.mdc       ← short always-on rules (uv, pins, secrets, English, skill)
├── Skills/
│   ├── install_skills.sh         ← symlink/copy skills into IDE discovery paths
│   ├── discord-docs/             ← Discord knowledge-base skill (§7)
│   │   ├── SKILL.md
│   │   ├── README.md
│   │   ├── index.md              ← curated page index (from llms.txt)
│   │   ├── commands/opencode/
│   │   └── scripts/
│   │       └── fetch_discord_docs.py
│   └── admin-helper/             ← guild admin CLI (members, channels, reports)
│       ├── SKILL.md
│       ├── README.md
│       ├── commands/opencode/
│       ├── workflows/
│       └── scripts/
│           └── admin_helper.py
├── docs/
│   ├── architecture.md           ← HTTP vs Gateway, discord_core, deployment
│   ├── developer-portal.md       ← checklist: create app, intents, install link, scopes
│   └── discord/                  ← local .md cache of official docs (generated; gitignored)
├── _shared/
│   ├── README.md
│   ├── discord_core/             ← shared package (§1.2)
│   │   ├── pyproject.toml
│   │   ├── src/discord_core/
│   │   └── tests/
│   └── scripts/
│       ├── GUIDE.md              ← script catalog (home-lab pattern)
│       ├── new-bot.sh            ← creates a bot from bots/_template
│       └── dev-tunnel.sh         ← local public tunnel (cloudflared/ngrok) for /interactions
├── bots/
│   ├── README.md                 ← bot index + status
│   ├── _template/                ← placeholder for new bots (same structure)
│   ├── heimdal/                  ← Onboarding
│   └── odin/                     ← Moderation (ASCII folder; "Odin" in prose)
└── tareas/
    ├── README.md                 ← open work board (one .md per task)
    └── *.md
```

### 2.1 Internal structure of each bot (`bots/<name>/`)

```text
bots/heimdal/
├── README.md            ← purpose, commands, permissions/intents, how to run, decisions
├── pyproject.toml       ← package `heimdal`, == pinned deps, script `heimdal = "heimdal.__main__:main"`
├── .env.example         ← DISCORD_APP_ID / DISCORD_PUBLIC_KEY / DISCORD_BOT_TOKEN / DISCORD_DEV_GUILD_ID / PORT
├── src/heimdal/
│   ├── __init__.py
│   ├── __main__.py      ← `uv run heimdal serve` / `sync-commands`
│   ├── settings.py
│   ├── commands/        ← command definitions (payloads) — one file per command
│   ├── handlers/        ← per-interaction logic (slash / component / modal)
│   ├── services/        ← domain logic (transport-agnostic)
│   ├── i18n/            ← string tables: en-US (default), es-ES
│   └── gateway/         ← (optional) discord.py client for events
├── scripts/
│   ├── README.md
│   ├── sync-commands.sh ← wrapper: `uv run heimdal sync-commands --guild $DISCORD_DEV_GUILD_ID`
│   ├── run-dev.sh       ← uvicorn --reload + load .env
│   └── smoke-test.sh    ← signed PING against the local endpoint
├── tests/               ← pytest (signature check, router, command payloads)
├── docs/                ← bot-specific design notes
├── logs/.gitkeep        ← *.log gitignored
└── reports/.gitkeep     ← script/audit outputs; gitignored except .gitkeep and README
```

Rule: `configs/` is not created by default (config goes through `.env` + `settings.py`); if a
bot needs config files (e.g. moderation rules in YAML), add `configs/`.

---

## 3. Example bots (placeholders with a real purpose)

### 3.1 Heimdal — Onboarding (the guardian of the bridge)

**Purpose:** receive and guide new members: welcome, rules, verification, self-assigned
interest roles.

| Interaction | Type | Phase | Doc notes |
|-------------|------|-------|-----------|
| `/welcome [user]` (es-ES: `/bienvenida`) | CHAT_INPUT | Base | message with Components v2 (`IS_COMPONENTS_V2`) + "I accept the rules" button |
| Button `rules_accept_<user_id>` | MESSAGE_COMPONENT | Base | `UPDATE_MESSAGE` (7) + assign role via `PUT /guilds/{g}/members/{u}/roles/{r}` |
| `/roles` | CHAT_INPUT | Base | string select `roles_pick` (multi) → interest role |
| `/introduce` (es-ES: `/presentarme`) | CHAT_INPUT | Base | opens **modal** (9) with text inputs; `MODAL_SUBMIT` publishes the card |
| Auto-welcome on join | Gateway `GUILD_MEMBER_ADD` | Extension | requires privileged intent `GUILD_MEMBERS` → document alternative: native Discord Onboarding + manual `/welcome` |

Bot permissions (guild install): `Send Messages`, `Manage Roles`, `Embed Links`. Scopes: `bot`, `applications.commands`. Contexts: `GUILD` (0).
`default_member_permissions` for `/welcome`: `MANAGE_GUILD` (`1 << 5`) for staff.

### 3.2 Odin — Moderation (the all-seeing)

**Purpose:** moderation tooling for staff plus an audit trail in `reports/`.

| Interaction | Type | Phase | Doc notes |
|-------------|------|-------|-----------|
| `/warn user reason` | CHAT_INPUT | Base | **ephemeral** reply to the mod + record in `reports/` (JSONL) |
| `/timeout user minutes` | CHAT_INPUT (`min_value`/`max_value`) | Base | `PATCH /guilds/{g}/members/{u}` `communication_disabled_until` |
| `/purge count` | CHAT_INPUT | Base | `deferred` (5) → bulk delete → `edit_original`; **destructive operation** (button confirmation) |
| "Report message" | MESSAGE (context menu) | Base | `target_id` + `resolved.messages` → mod channel |
| "View history" | USER (context menu) | Base | reads the user's `reports/`, ephemeral |
| `/automod` | CHAT_INPUT (subcommands) | Extension | Discord AutoMod API (no `MESSAGE_CONTENT` intent) |

Bot permissions: `Moderate Members`, `Manage Messages`, `Kick/Ban Members` (only if `/ban` is
implemented), `Read Message History`. Bot-wide `default_member_permissions`: `MODERATE_MEMBERS`
(`1 << 40`). Contexts: `GUILD`. Installation: **Guild Install only**.

### 3.3 `bots/_template/`

Minimal copy with a template `README.md` (sections: Purpose · Commands · Permissions/Intents ·
Variables · Run · Decisions · Pending), `pyproject.toml`, `.env.example`, `src/<bot>/` with a
working `/ping`, `scripts/`, `tests/`, `i18n/`, `logs/`, `reports/`.
`_shared/scripts/new-bot.sh <name> "<purpose>"` clones and renames it.

---

## 4. Root documents (adapted from `home-lab`)

### 4.1 `README.md` (English, human)

Keeps the style of `home-lab/README.md`: opening paragraph, core documents table, repository
structure tree, bot table (instead of hosts), and summarized agent rules linking to `AGENTS.md`.
Everything network/SSH/K3s-specific is dropped. Content:

1. What it is: Discord bot monorepo (Python 3.14 + uv), one per folder, common `discord_core`.
2. Bot table: `Heimdal` (onboarding) · `Odin` (moderation) · `_template`.
3. Quickstart: `uv sync` → copy `.env.example` → `bash bots/heimdal/scripts/sync-commands.sh` → `bash bots/heimdal/scripts/run-dev.sh` → tunnel → paste URL into the Developer Portal.
4. Links: `docs/architecture.md`, `docs/developer-portal.md`, `tareas/`, `discord-docs` skill.
5. A one-line note that all code and technical docs are in English (§1.4).

### 4.2 `AGENTS.md` (English, LLM)

Kept from the original: **Last modified** header, **RULES** block, **Source of truth map**,
**Layout conventions**, **Essential commands**, **Build / test / lint reality**, **Code patterns**,
**High-risk gotchas**, **Destructive operations policy**, **If you update this file later**.
Dropped: network topology, SSH, K3s, Traefik, Portainer, Graphify, RTK, sibling repos (except a
pointer to `home-lab` as the future deployment repo).

New repo-specific rules:

- **English only** for all code, identifiers, comments, docstrings, tests, logs, commit messages
  and technical docs (§1.4). Discord-facing strings default to `en-US` with `es-ES` localizations.
- New Python → **uv** only, **Python 3.14**, `==` pins, commit `uv.lock`; one workspace lock at root.
- **Never** commit `.env`, tokens, or public keys of real apps; `.env.example` with placeholders only.
- Interaction handlers must answer within **3 s** or defer; long work → `deferred` + `edit_original`.
- **Destructive Discord ops need an explicit user yes**: `/purge`, ban/kick, bulk overwrite of
  **global** commands (`PUT /applications/{id}/commands` with a different set deletes the missing
  ones), deleting commands, changing bot permissions/intents in the Portal.
- Register commands to the **dev guild** first (instant); global only when asked.
- One bot ↔ one Application ID; never share tokens between bots.
- Before answering Discord API questions, use the `discord-docs` skill (local cache first).
- Logs → nearest `logs/`; script outputs/audits → nearest `reports/`; both gitignored except `.gitkeep`.
- Root `README.md` and this file are English technical documentation.

### 4.3 `.cursor/rules/discord-bot.mdc` (always-on, ≤ 15 lines)

Reminds: English-only code/comments, uv/3.14/pins, secrets, `discord-docs` skill, deferred if > 3 s,
destructive policy.

---

## 5. Support files

### `.gitignore`

```gitignore
.env
.env.*
!.env.example
**/logs/*
!**/logs/.gitkeep
**/reports/*
!**/reports/.gitkeep
!**/reports/README.md
docs/discord/            # official docs cache (regenerable)
Skills/*/.install-manifest
.cursor/skills/          # IDE install target (Skills/ is the source)
.github/skills/
.opencode/skills/
.opencode/commands/
.claude/skills/
.agents/skills/
.venv/
**/__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
dist/
```

### Root `pyproject.toml`

```toml
[project]
name = "discord-bot-workspace"
version = "0.0.0"
requires-python = "==3.14.*"

[tool.uv.workspace]
members = ["_shared/discord_core", "bots/*"]
exclude = ["bots/_template"]

[tool.uv]
package = false

[dependency-groups]
dev = ["ruff==0.16.6", "pytest==9.1.1", "pytest-asyncio==1.4.0"]

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
extend-select = ["N", "D"]   # naming + docstring conventions (English-only policy support)

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["_shared/discord_core/tests", "bots/*/tests"]
```

### Bot `pyproject.toml` (Heimdal example)

```toml
[project]
name = "heimdal"
version = "0.1.0"
description = "Heimdal — onboarding bot (welcome, rules, roles)"
readme = "README.md"
requires-python = "==3.14.*"
dependencies = ["discord-core"]

[project.optional-dependencies]
gateway = ["discord.py==2.7.1"]

[project.scripts]
heimdal = "heimdal.__main__:main"

[tool.uv.sources]
discord-core = { workspace = true }

[build-system]
requires = ["hatchling==1.32.0"]
build-backend = "hatchling.build"
```

`discord_core/pyproject.toml` pins `httpx`, `PyNaCl`, `fastapi`, `uvicorn[standard]`,
`pydantic`, `pydantic-settings`, `structlog` with `==`.

---

## 6. Execution phases

| Phase | Deliverable | Verification |
|-------|-------------|--------------|
| **0. Skeleton** | `.gitignore`, `.python-version`, root `pyproject.toml`, folder tree with `.gitkeep`, `tareas/README.md` | `uv sync` without errors; `git status` free of secrets |
| **1. Root docs** | `README.md`, `AGENTS.md`, `.cursor/rules/discord-bot.mdc`, `docs/architecture.md`, `docs/developer-portal.md`, `_shared/scripts/GUIDE.md`, `bots/README.md` | Internal links resolve (`rg` on paths); AGENTS in English and dated |
| **2. `discord_core`** | Modules §1.2 + tests: Ed25519 signature (valid/invalid vector), `PONG`, router by `custom_id`, command serialization incl. localizations, HTTP client with mocked 429 | `uv run pytest _shared/discord_core` green; `uv run ruff check .` |
| **3. `bots/_template` + `new-bot.sh`** | Working `/ping` bot end-to-end locally | `bash scripts/smoke-test.sh` sends signed `PING` → `{"type":1}`; signed `/ping` interaction → callback 4 |
| **4. Heimdal (base)** | §3.1 Base commands, full README, `.env.example`, scripts, `i18n/es-ES` | `sync-commands` to dev guild (diff printed, no global deletes); manual test on a test server |
| **5. Odin (base)** | §3.2 Base commands, `reports/` JSONL + format README, `/purge` confirmation | same + unit test for the report log |
| **6. `discord-docs` skill** | §7 complete, local cache generated | Invoke the skill and resolve a question (e.g. "choices limit") using the local cache only |
| **7. Deployment (pending, `tareas/`)** | Dockerfile per bot (`uv` multi-stage), dev tunnel, Traefik/Cloudflare route in `home-lab`, `GET /healthz` healthcheck | Out of scope for the foundations; a task is opened |

Extensions (open tasks): Gateway for `GUILD_MEMBER_ADD` in Heimdal; AutoMod in Odin; CI
(ruff + pytest); persistence (SQLite/Postgres) replacing JSONL; additional locales beyond `es-ES`.

---

## 7. `discord-docs` skill (official knowledge base)

**Location:** `Skills/discord-docs/` (portable Agent Skill, versioned with the repo).
Install into IDE discovery paths with `./Skills/install_skills.sh` (symlinks
`.cursor/skills/`, `.github/skills/`, `.opencode/skills/`, `.claude/skills/`,
`.agents/skills/` — those folders are gitignored). OpenCode command: `/discord.docs`.

**Frontmatter:**

```yaml
name: discord-docs
description: >-
  Knowledge base of the official Discord Developers documentation (interactions,
  application commands, reference, gateway, components, permissions). Consults the
  local cache docs/discord/*.md first and, if missing, downloads the official page in
  .md format. Triggers: "discord docs", "documentación de discord", "how do I do X in
  the Discord API", interaction, slash command, callback type, ephemeral, modal,
  snowflake, rate limit, intents, bot permissions, Developer Portal.
```

**`SKILL.md` content (≤ 150 lines, English):**

1. **Mandatory lookup order:** (1) local `docs/discord/<path>.md` → (2)
   `python Skills/discord-docs/scripts/fetch_discord_docs.py <slug|--all>` to
   fetch/refresh → (3) only then web search. Never invent endpoints, enum values or limits:
   cite the page and section.
2. **Curated index (`index.md`):** table *topic → official URL → local path*, starting with
   the 5 base pages plus the essentials from `llms.txt`: Components (overview, message
   components, modals, reference), Gateway (events, intents, "you might not need a privileged
   intent"), Permissions, OAuth2, Rate Limits, Webhooks, Resources (Guild, Channel, Message,
   User, Application, Auto Moderation), Change Log.
3. **Constants cheat sheet** (to avoid re-reading): interaction types 1–5, callback types 1–12,
   flags `EPHEMERAL=64` / `IS_COMPONENTS_V2=32768`, option types 1–11, command types 1–4,
   contexts 0–2, deadlines 3 s / 15 min, v10 base URL, `User-Agent` format.
4. **Recipes** with source reference: verify signature in Python (`PyNaCl`), answer `PING`,
   register guild vs global command, deferred + edit original, modal → submit, context menu
   with `target_id`, `default_member_permissions` bitfield, `name_localizations`.
5. **Answer format:** short answer + `docs.discord.com/...#section` citation + local path read,
   if any.

**`scripts/fetch_discord_docs.py`** (stdlib only, no deps): reads `index.md` (or `llms.txt`
with `--all`), downloads each `URL + ".md"` to `docs/discord/<path>.md`, writes
`docs/discord/_SOURCE.md` with date and page list. Idempotent; `--check` compares hashes to
detect upstream changes (prints a table; `reports/` does not apply, it is repo-level).

---

## 8. Risks and points to confirm

| Topic | Risk | Proposal |
|-------|------|----------|
| HTTP vs Gateway for onboarding | Automatic welcome on join needs Gateway + privileged intent `GUILD_MEMBERS` (approval once the bot exceeds 100 servers; on your own server toggling it in the Portal is enough) | HTTP base + manual `/welcome`; Gateway as a documented extension |
| Folder name `odin` vs `Odin` | Accents in paths/Python packages break imports and shells | Folder and package `odin`; "Odin" in prose |
| English-first Discord strings | Spanish-speaking members see English if the client locale is not `es-ES` (Discord picks localization by user locale) | `es-ES` localizations shipped from day one; `es-419` added as a follow-up task |
| Public endpoint | Discord validates the endpoint when saved and audits signatures periodically; downtime → Discord removes the URL and emails you | Healthcheck + stable deployment task in `home-lab` (Traefik/Cloudflare) |
| Global command `PUT` | Overwrites the full set: commands not included are deleted | Sync script always prints a diff and requires `--yes` for global |
| Pinned versions | Go stale | Periodic `uv lock --upgrade` task + tests |
| `reports/` with user IDs | Personal data | Gitignored; README states retention and deletion |

---

## 9. Reference commands (after phases 0–5)

```bash
uv sync                                                      # whole workspace
uv run ruff check . && uv run pytest                         # quality
cp bots/heimdal/.env.example bots/heimdal/.env                # fill from the Developer Portal
bash bots/heimdal/scripts/sync-commands.sh                   # commands → dev guild
bash bots/heimdal/scripts/run-dev.sh                         # uvicorn :8000
bash _shared/scripts/dev-tunnel.sh 8000                      # public URL → Portal › Interactions Endpoint URL
bash bots/heimdal/scripts/smoke-test.sh                      # local signed PING
bash _shared/scripts/new-bot.sh thor "Events bot"            # new bot from _template
python Skills/discord-docs/scripts/fetch_discord_docs.py --all   # refresh docs cache
./Skills/install_skills.sh --auto --skill discord-docs          # IDE discovery paths
```
