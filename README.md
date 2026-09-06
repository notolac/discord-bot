# discord-bot

Monorepo of Discord bots built with **Python 3.14 + uv**, one bot per folder, built on the
official API's **HTTP Interactions** model (FastAPI endpoint with Ed25519 verification) and
a minimal shared library (`discord_core`). All code and technical documentation are in
**English**; see [AGENTS.md](AGENTS.md).

## Core documents

| Document | Purpose |
|-----------|----------|
| **[AGENTS.md](AGENTS.md)** | Rules for LLM agents: uv/3.14, secrets, destructive operations, 3 s / deferred responses, and the docs skill |
| **[PLAN-IMPLEMENTACION.md](PLAN-IMPLEMENTACION.md)** | Implementation plan and phases |
| **[docs/architecture.md](docs/architecture.md)** | HTTP vs Gateway, `discord_core`, and deployment |
| **[docs/developer-portal.md](docs/developer-portal.md)** | Developer Portal checklist: app creation, keys, intents, install link, and endpoint |
| **[bots/README.md](bots/README.md)** | Bot inventory and status |
| **[_shared/discord_core/README.md](_shared/discord_core/README.md)** | Shared library modules |
| **[_shared/scripts/GUIDE.md](_shared/scripts/GUIDE.md)** | Script catalog |
| **[.cursor/skills/discord-docs/SKILL.md](.cursor/skills/discord-docs/SKILL.md)** | Official Discord documentation knowledge base (local mirror in `docs/discord/`) |
| **[tareas/](tareas/README.md)** | Open work: deployment, CI, Gateway, AutoMod, and persistence |

## Bots

| Bot | Purpose | Folder | Status |
|-----|-----------|---------|--------|
| **Heimdal** | Onboarding: welcome with rules acceptance, interest roles, and an introduction modal | [bots/heimdal/](bots/heimdal/README.md) | Base implemented, not deployed |
| **Odin** | Moderation: `/warn`, `/timeout`, `/purge` with confirmation, "Report message", "View history", and a JSONL log | [bots/odin/](bots/odin/README.md) | Base implemented, not deployed |
| `_template` | Template for new bots (`/ping`) | [bots/_template/](bots/_template/README.md) | — |

Each bot is a **separate application** in the Developer Portal with its own Application ID and token.

## Repository structure

```text
discord-bot/
├── README.md                  ← this file
├── AGENTS.md                  ← LLM agent rules
├── PLAN-IMPLEMENTACION.md     ← implementation plan
├── pyproject.toml / uv.lock   ← uv workspace (virtual root listing all members)
├── .python-version            ← 3.14
├── .cursor/
│   ├── rules/discord-bot.mdc  ← always-on reminder
│   └── skills/discord-docs/   ← skill and official docs mirror script
├── docs/                      ← architecture.md · developer-portal.md · discord/ (mirror, gitignored)
├── _shared/
│   ├── discord_core/          ← shared library (src/ + tests/)
│   └── scripts/               ← new-bot.sh · dev-tunnel.sh · GUIDE.md
├── bots/
│   ├── _template/             ← template
│   ├── heimdal/               ← onboarding
│   └── odin/                  ← moderation
└── tareas/                    ← open-work board
```

Each bot contains: `src/<bot>/` · `i18n/` · `scripts/` · `tests/` · `docs/` · `logs/` · `reports/` · `README.md` · `.env.example`.

## Quick start

```bash
uv sync                                          # install the whole workspace
uv run ruff check . && uv run pytest -q          # quality checks
cp bots/heimdal/.env.example bots/heimdal/.env   # fill from the Developer Portal
bash bots/heimdal/scripts/smoke-test.sh          # offline endpoint self-test
bash bots/heimdal/scripts/sync-commands.sh       # commands → test server (DISCORD_DEV_GUILD_ID)
bash bots/heimdal/scripts/run-dev.sh             # http://127.0.0.1:8000/interactions
bash _shared/scripts/dev-tunnel.sh 8000          # public URL → Portal › Interactions Endpoint URL
```

Create a new bot with `bash _shared/scripts/new-bot.sh thor "Events bot"`.

## Agent rules (human summary)

The complete rules are in **[AGENTS.md](AGENTS.md)**:

- Code, comments, tests, and technical docs are **English-only**; Discord text uses `en-US` with `es-ES` translations in `i18n/`.
- **uv** + Python **3.14**, dependencies pinned with `==`, and one `uv.lock`.
- Never commit `.env` files, tokens, or real keys.
- Destructive operations (purge, ban, global command sync that deletes commands, and Portal changes) require **explicit user approval**.
- Register commands to the test server first; use global registration only when requested.
- For API questions, use the `discord-docs` skill: local mirror first, then download, then web.
