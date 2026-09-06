---
name: admin-helper
description: >
  Guild administration via Discord HTTP API v10 for operators who deploy these
  bots. Lists members for reports, searches members without a privileged intent,
  lists/creates/edits/deletes channels, and reads audit logs using a bot token.
  Triggers: admin-helper, member report, list members, create channel, edit
  channel, delete channel, guild channels, audit log, /discord.admin.
---

# admin-helper — guild admin via Discord REST

Portable skill for **any LLM agent** with shell access. Human overview: [README.md](./README.md).
Official API facts come from the **`discord-docs` skill** — do not invent endpoints, enums, or
limits. Cite the page.

CLI (Python 3.14 via `uv`; never bare `python3`):

```bash
./Skills/admin-helper/scripts/admin_helper [--env-file PATH] [--guild ID] [--json] <command> [args]
uv run --python 3.14 Skills/admin-helper/scripts/admin_helper.py <command> [args]
```

Prefer `--json` when parsing output. Prefer `--env-file bots/<bot>/.env` over pasting tokens.

## Credentials

Validate **before every API call**. Stop if missing.

```bash
: "${DISCORD_BOT_TOKEN:?Set DISCORD_BOT_TOKEN}"
```

| Variable | Purpose |
|----------|---------|
| `DISCORD_BOT_TOKEN` | Bot token (`Authorization: Bot <token>`). One bot ↔ one token. |
| `DISCORD_GUILD_ID` | Default guild snowflake (optional). Overrides the dev fallback. |
| `DISCORD_DEV_GUILD_ID` | Test guild; implicit fallback if `--guild` / `DISCORD_GUILD_ID` are unset. |
| `DISCORD_PROD_GUILD_ID` | Production guild (optional). **Never** an implicit default — pass `--guild` with this value. |

`--env-file` loads `KEY=VALUE` **without overriding** variables already in the environment.
Never print the token. Never commit `.env`.

Smoke test: `./Skills/admin-helper/scripts/admin_helper --env-file bots/heimdal/.env --json me`

Expect HTTP 200 and the bot user (`bot: true`). On 401 the token is wrong or revoked.

## HTTP conventions (from official docs)

- Base: `https://discord.com/api/v10`
- Headers: `Authorization: Bot <token>`, `User-Agent: DiscordBot ($url, $version)`, `Content-Type: application/json`
- Writes: `X-Audit-Log-Reason` (1–512 URL-encoded UTF-8 chars) via `--reason`
- 429: wait `retry_after` (CLI retries). Do not hard-code rate limits.
- Snowflakes are **strings**.

Citations: [reference](https://docs.discord.com/developers/reference) · local `docs/discord/reference.md`;
[rate limits](https://docs.discord.com/developers/topics/rate-limits) · `docs/discord/topics/rate-limits.md`.

## Destructive ops (mandatory)

Treat as destructive unless the user **explicitly** approved in this chat:

- `channel-create`, `channel-edit`, `channel-move`
- `channel-delete` (guild channels **cannot be undone**)

Then pass `--yes`. Do not pass `--yes` on your own. CLI flags are not a substitute for user
approval (`AGENTS.md`). Reads (`me`, `guilds`, `channels`, `members`, `audit`, reports) do not
need `--yes`.

## Commands and APIs

| CLI | HTTP | Permission / intent | Docs |
|-----|------|---------------------|------|
| `me` | `GET /users/@me` | token | resources/user § Get Current User |
| `guilds` | `GET /users/@me/guilds?with_counts=true` | token | resources/user § Get Current User Guilds |
| `guild [id]` | `GET /guilds/{id}?with_counts=true` | in guild | resources/guild § Get Guild |
| `channels [id]` | `GET /guilds/{id}/channels` | `VIEW_CHANNEL` (from 2026-11-16 hidden otherwise) | resources/guild § Get Guild Channels |
| `channel <id>` | `GET /channels/{id}` | view channel | resources/channel § Get Channel |
| `roles [id]` | `GET /guilds/{id}/roles` | in guild | resources/guild § Get Guild Roles |
| `role-counts [id]` | `GET /guilds/{id}/roles/member-counts` | in guild | resources/guild § Get Guild Role Member Counts |
| `member <user_id>` | `GET /guilds/{id}/members/{user}` | in guild | resources/guild § Get Guild Member |
| `members [id]` | `GET /guilds/{id}/members` paginated (`limit` 1–1000, `after`) | **`GUILD_MEMBERS` intent** | resources/guild § List Guild Members |
| `members-search <query>` | `GET /guilds/{id}/members/search` | none extra | resources/guild § Search Guild Members |
| `members-report [id]` | list members → `reports/admin-helper/` | **`GUILD_MEMBERS` intent** | same + reports/README.md |
| `audit [id]` | `GET /guilds/{id}/audit-logs` | `VIEW_AUDIT_LOG` (`1<<7`) | resources/audit-log § Get Guild Audit Log |
| `channel-create` | `POST /guilds/{id}/channels` | `MANAGE_CHANNELS` (`1<<4`) | resources/guild § Create Guild Channel |
| `channel-edit` | `PATCH /channels/{id}` | `MANAGE_CHANNELS` | resources/channel § Modify Channel |
| `channel-delete` | `DELETE /channels/{id}` | `MANAGE_CHANNELS` | resources/channel § Delete/Close Channel |
| `channel-move` | `PATCH /guilds/{id}/channels` | `MANAGE_CHANNELS` | resources/guild § Modify Guild Channel Positions |

Channel `type` names: `text` 0 · `voice` 2 · `category` 4 · `announcement` 5 · `stage` 13 · `forum` 15 · `media` 16
([channel types](https://docs.discord.com/developers/resources/channel#channel-object-channel-types)).
Name 1–100 characters. `--parent` is a category snowflake. Community Rules / Updates channels cannot be deleted.

Guild id: positional (most list commands) or `--guild` / `DISCORD_GUILD_ID` /
`DISCORD_DEV_GUILD_ID`. To hit production, pass `--guild` with `DISCORD_PROD_GUILD_ID`
(do not rely on env fallback). `member` and `members-search` take the user/query only —
guild from `--guild` or env.

## Member lists vs privileged intent

`List Guild Members` **requires** Server Members Intent (`GUILD_MEMBERS`). HTTP-only bots in this
repo leave it **off** by default (`docs/developer-portal.md`). Alternatives **without** the intent:

- `member <user_id>` — known id
- `members-search <prefix>` — username/nickname prefix
- `guild --json` — `approximate_member_count` with `with_counts=true`
- `role-counts` — per-role counts (no `@everyone`)

If `members` / `members-report` returns 403, explain the intent and the alternatives. Do not enable
Portal intents without explicit user approval.

Citation: [You might not need a privileged intent](https://docs.discord.com/developers/gateway/you-might-not-need-a-privileged-intent)
· local `docs/discord/gateway/you-might-not-need-a-privileged-intent.md`.

## Reports

`members-report` writes gitignored files under `reports/admin-helper/` (user IDs). Formats:
`--format md|csv|jsonl`. Do not `git add` them. Retention: [`reports/README.md`](../../reports/README.md).

Workflow: [workflows/member_report.md](workflows/member_report.md).

## New endpoints

If the user asks for an admin action this CLI does not wrap, load **`discord-docs`**, read the
local mirror, then either extend the CLI or call the documented route through this skill's HTTP
rules (same token, User-Agent, 429 handling, `--yes` for writes). Never invent paths.

## Checklist

```
- [ ] Token via env / --env-file; never printed
- [ ] Correct guild snowflake (dev fallback vs explicit `--guild` for `DISCORD_PROD_GUILD_ID`)
- [ ] Reads: run CLI, summarize, cite docs page
- [ ] Member enumeration: intent on, or use search / get-by-id / counts
- [ ] Writes: user said yes in chat, then --yes, then --reason when useful
- [ ] Reports stay under reports/admin-helper/ (gitignored)
```
