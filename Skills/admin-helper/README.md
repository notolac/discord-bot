# admin-helper

Portable agent skill for **guild administration** over Discord HTTP API v10. Operators who deploy
Heimdal/Odin (or any bot in this monorepo) can list members for reports and create/edit/delete
channels using a bot token — from any IDE agent, not only Cursor.

Works with any LLM agent that can read markdown and run shell/Python. Agent instructions:
[`SKILL.md`](./SKILL.md). APIs are taken from the official docs via [`discord-docs`](../discord-docs/).

## File layout

| Path | Audience | Purpose |
|------|----------|---------|
| [`README.md`](./README.md) | Humans | Setup, install, command reference |
| [`SKILL.md`](./SKILL.md) | LLM agents | Auth, endpoints, intent caveats, `--yes` policy |
| [`scripts/admin_helper`](./scripts/admin_helper) | Users & agents | CLI wrapper (Python 3.14 via `uv`) |
| [`scripts/admin_helper.py`](./scripts/admin_helper.py) | Users & agents | CLI implementation (stdlib-only) |
| [`workflows/member_report.md`](./workflows/member_report.md) | Agents | How to produce a member report |

## Install the skill

From the repo root:

```bash
./Skills/install_skills.sh --auto --skill admin-helper
./Skills/install_skills.sh --sync
```

Reload the IDE. In OpenCode invoke **`/discord.admin`**. See
[repo README — Agent Skills](../../README.md#agent-skills-skills).

## Prerequisites

Use the bot that is **already in** the target guild(s). One Application ID ↔ one token.

```bash
export DISCORD_BOT_TOKEN="…"           # or: --env-file bots/heimdal/.env
export DISCORD_GUILD_ID="…"            # optional default (overrides DISCORD_DEV_GUILD_ID)
# DISCORD_PROD_GUILD_ID lives in the bot .env; pass it with --guild (never implicit)
```

The bot needs guild permissions matching the action: `VIEW_CHANNEL` to list channels,
`MANAGE_CHANNELS` (`1<<4`) to create/edit/delete, `VIEW_AUDIT_LOG` (`1<<7`) for `audit`.
Role hierarchy still applies (bot role above what it manages).

**Full member lists** (`members`, `members-report`) need **Server Members Intent**
(`GUILD_MEMBERS`) in the Developer Portal. That intent is off by default for HTTP-only bots.
Without it, use `members-search`, `member <user_id>`, `guild` (approximate counts), or
`role-counts`. Enabling a privileged intent is a Portal change — ask the owner first.

## CLI

Run from the **repo root**. Never bare `python3`. Global flags (`--env-file`, `--guild`, `--json`)
go **before** the subcommand.

```bash
./Skills/admin-helper/scripts/admin_helper --env-file bots/heimdal/.env --json me
./Skills/admin-helper/scripts/admin_helper --env-file bots/heimdal/.env guilds
./Skills/admin-helper/scripts/admin_helper --guild GUILD_ID channels
./Skills/admin-helper/scripts/admin_helper --guild GUILD_ID members-report --format csv
# production: --guild <DISCORD_PROD_GUILD_ID from the bot .env>  (not the implicit default)
```

| Command | Writes to Discord? |
|---------|-------------------|
| `me` · `guilds` · `guild` · `channels` · `channel` · `roles` · `role-counts` | No |
| `member` · `members` · `members-search` · `members-report` · `audit` | No (report is local) |
| `channel-create` · `channel-edit` · `channel-move` | **Yes** (`--yes` after approval) |
| `channel-delete` | **Yes**, irreversible for guild channels |

`--json` prints JSON (better for agents). `--reason` sets `X-Audit-Log-Reason` on writes.

### Channel types

`text` (0), `voice` (2), `category` (4), `announcement` (5), `stage` (13), `forum` (15), `media` (16).

```bash
./Skills/admin-helper/scripts/admin_helper --guild GUILD_ID \
  channel-create --name reports --type text --parent CATEGORY_ID --reason "ops" --yes
```

## Reports

Member exports land in [`reports/admin-helper/`](../../reports/README.md) (gitignored; contain
user IDs). Override with `--out PATH`.

## Tests

```bash
uv run pytest Skills/admin-helper/tests -q
```

No network: HTTP is mocked.

## See also

- [`SKILL.md`](./SKILL.md) — agent instructions
- [`../discord-docs/SKILL.md`](../discord-docs/SKILL.md) — official docs lookup
- [`docs/developer-portal.md`](../../docs/developer-portal.md) — intents and install permissions
- [`AGENTS.md`](../../AGENTS.md) — destructive-operations policy
