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
| **[Skills/discord-docs/SKILL.md](Skills/discord-docs/SKILL.md)** | Official Discord documentation knowledge base (local mirror in `docs/discord/`) |
| **[Skills/admin-helper/SKILL.md](Skills/admin-helper/SKILL.md)** | Guild admin via REST: member reports and channel create/edit/delete |
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
├── .cursor/rules/             ← Cursor always-on reminder (IDE install targets are gitignored)
├── Skills/
│   ├── install_skills.sh      ← symlink/copy skills into Cursor, Copilot, OpenCode, Claude, Codex
│   ├── discord-docs/          ← portable skill + official docs mirror script
│   └── admin-helper/          ← guild admin CLI (members, channels, reports)
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
./Skills/install_skills.sh --auto                # skill → IDE discovery paths
uv run ruff check . && uv run pytest -q          # quality checks
cp bots/heimdal/.env.example bots/heimdal/.env   # fill from the Developer Portal
bash bots/heimdal/scripts/smoke-test.sh          # offline endpoint self-test
bash bots/heimdal/scripts/sync-commands.sh       # commands → DISCORD_DEV_GUILD_ID (not prod)
bash bots/heimdal/scripts/run-dev.sh             # http://127.0.0.1:8000/interactions
bash _shared/scripts/dev-tunnel.sh 8000          # public URL → Portal › Interactions Endpoint URL
```

Create a new bot with `bash _shared/scripts/new-bot.sh thor "Events bot"`.

## Agent Skills (`Skills/`)

Repo-local [Agent Skills](https://agentskills.io). Each subdirectory with a `SKILL.md` file is
one skill. Source of truth is `Skills/`; IDE folders (`.cursor/skills/`, `.github/skills/`,
`.opencode/skills/`, `.claude/skills/`, `.agents/skills/`) are install targets and gitignored.

| Skill | Purpose |
|-------|---------|
| [discord-docs](Skills/discord-docs/) | Official Discord Developers docs: local mirror `docs/discord/` + fetch script |
| [admin-helper](Skills/admin-helper/) | Guild admin via REST: member reports, create/edit/delete channels (`/discord.admin`) |

Human overview: [`Skills/discord-docs/README.md`](Skills/discord-docs/README.md),
[`Skills/admin-helper/README.md`](Skills/admin-helper/README.md). Agent instructions live in
each skill's `SKILL.md`.

### Install into your IDE

From the repo root:

```bash
./Skills/install_skills.sh
```

Interactive wizard: sync missing skills, quick install (detected IDE, project, symlink),
custom install (scope / IDE / symlink-or-copy), or uninstall.

Non-interactive:

```bash
./Skills/install_skills.sh --auto                      # all skills
./Skills/install_skills.sh --sync                      # only new/missing (reuse prior IDE prefs)
./Skills/install_skills.sh --auto --skill discord-docs # one skill
./Skills/install_skills.sh --skills                    # list discoverable skills
./Skills/install_skills.sh --uninstall --all
```

Skills are **auto-discovered** from `Skills/*/SKILL.md` (no allowlist). After adding a new
skill folder, run `--sync` (or `--auto`) so IDE paths pick it up.

After install, reload your IDE. OpenCode command wrappers use `discord.*` names
(`/discord.docs`, `/discord.admin`). Command definitions stay with each skill at
`Skills/<name>/commands/opencode/`. Per-skill install state is stored in
`Skills/<name>/.install-manifest` (gitignored).

## Agent rules (human summary)

The complete rules are in **[AGENTS.md](AGENTS.md)**:

- Code, comments, tests, and technical docs are **English-only**; Discord text uses `en-US` with `es-ES` translations in `i18n/`.
- **uv** + Python **3.14**, dependencies pinned with `==`, and one `uv.lock`.
- Never commit `.env` files, tokens, or real keys.
- Destructive operations (purge, ban, global command sync that deletes commands, Portal changes, and **admin-helper** channel create/edit/delete) require **explicit user approval**.
- Register commands to the test server first (`DISCORD_DEV_GUILD_ID`). Production is `DISCORD_PROD_GUILD_ID` in the same `.env` — pass `--guild`; it is never the implicit default. Global registration only when requested.
- For API questions, use the `discord-docs` skill: local mirror first, then download, then web.
