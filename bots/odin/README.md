# Odin — moderation

Odin, the all-seeing, gives staff the day-to-day moderation tools and keeps an audit trail in
`reports/`. Onboarding belongs to [Heimdal](../heimdal/README.md). Odin does **not** read
message content proactively (no `MESSAGE_CONTENT` intent); automated filtering is a future
AutoMod integration.

## Commands

| Command | Type | Who | Flow |
|---------|------|-----|------|
| `/warn user reason` (es: `/avisar`) | CHAT_INPUT | `MODERATE_MEMBERS` | Appends a `warn` record, posts a notice to `ODIN_MOD_CHANNEL_ID`, ephemeral confirmation |
| `/timeout user minutes [reason]` (es: `/silenciar`) | CHAT_INPUT | `MODERATE_MEMBERS` | `PATCH /guilds/{g}/members/{u}` with `communication_disabled_until` (1–40320 min), record + notice |
| `/purge count` (es: `/limpiar`) | CHAT_INPUT | `MANAGE_MESSAGES` | Ephemeral confirmation with **Delete N** / **Cancel** buttons. Confirm → deferred update → `GET messages` → `bulk-delete` (skips > 14 days) → edits the confirmation with the result. **Destructive** |
| **Report message** (es: *Reportar mensaje*) | MESSAGE context menu | Everyone | Uses `target_id` + `resolved.messages`; forwards author, excerpt and jump link to the mod channel; appends a `report` record |
| **View history** (es: *Ver historial*) | USER context menu | `MODERATE_MEMBERS` | Ephemeral list of the last `ODIN_HISTORY_LIMIT` records about the member |

Command payloads: `uv run odin list-commands`.

## Permissions / intents

- Installation context: **Guild Install** only. Scopes: `bot`, `applications.commands`.
- Bot permissions: `Moderate Members`, `Manage Messages`, `Read Message History`,
  `Send Messages`. Add `Kick Members` / `Ban Members` only when those commands exist.
- Gateway intents: none — HTTP interactions only.

## Variables

See [`.env.example`](.env.example). Shared variables: [`bots/_template/README.md`](../_template/README.md#variables).

| Variable | Required | Description |
|----------|----------|-------------|
| `ODIN_MOD_CHANNEL_ID` | for reports | Channel for reports and notices; without it `/warn` and `/timeout` still record locally |
| `ODIN_REPORTS_DIR` | no | JSONL log directory (default `bots/odin/reports/`) |
| `ODIN_HISTORY_LIMIT` | no | Entries shown by *View history* (default 10, max 25) |

## Audit log format (`reports/moderation-<guild_id>.jsonl`)

One JSON object per line:

```json
{"action":"warn","guild_id":"…","moderator_id":"…","target_id":"…","reason":"spam","channel_id":"…","extra":{},"timestamp":"2026-09-06T09:00:00+00:00"}
```

`action` ∈ `warn | timeout | purge | report`. `extra` carries action-specific data
(`minutes`/`until`, `requested`/`deleted`, `message_id`/`excerpt`). Files are gitignored
(they contain user IDs) — see [`reports/README.md`](reports/README.md).

## Run

```bash
uv sync
cp bots/odin/.env.example bots/odin/.env            # fill it
bash bots/odin/scripts/smoke-test.sh                # offline self-test
bash bots/odin/scripts/sync-commands.sh             # commands → DISCORD_DEV_GUILD_ID
bash bots/odin/scripts/run-dev.sh                   # http://127.0.0.1:8001/interactions
bash _shared/scripts/dev-tunnel.sh 8001             # public URL → Developer Portal
uv run pytest bots/odin
```

## Layout

```text
src/odin/          commands.py · handlers.py · settings.py · __main__.py · services/report_log.py
i18n/              en-US.json (default) · es-ES.json
scripts/           run-dev.sh · sync-commands.sh · smoke-test.sh  (see scripts/README.md)
tests/             pytest
docs/              design notes
logs/ reports/     runtime output (gitignored)
```

## Decisions

- **Two-step `/purge`.** Destructive operations always confirm through a button; the delete
  runs in a deferred handler (`DEFERRED_UPDATE_MESSAGE` → *edit original*), so the 3 s limit
  never applies to the API calls.
- **JSONL instead of a database** for the first iteration — trivial to inspect, no infra.
  Migration tracked in [`tareas/persistence.md`](../../tareas/persistence.md).
- **No `MESSAGE_CONTENT` intent.** Report content comes from `resolved.messages` of the
  context-menu interaction, which Discord provides without privileged intents.

## Pending

- [ ] `/automod` subcommands on top of Discord's AutoMod API ([`tareas/automod.md`](../../tareas/automod.md)).
- [ ] `/ban` / `/kick` with confirmation (adds `BAN_MEMBERS` / `KICK_MEMBERS`).
- [ ] Filter `/purge` by author.
