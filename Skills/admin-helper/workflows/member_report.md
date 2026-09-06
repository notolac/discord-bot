# Member report workflow

Use with the `admin-helper` CLI. Do not invent Discord endpoints; see [`SKILL.md`](../SKILL.md)
and `discord-docs`.

## When to use

The operator wants a member list for a report, audit, or spreadsheet: usernames, join dates,
roles, bot/pending flags.

## Steps

1. Confirm guild snowflake (`guilds`, `--guild`, `DISCORD_GUILD_ID`, or `DISCORD_DEV_GUILD_ID`).
   Production is `DISCORD_PROD_GUILD_ID` — pass it with `--guild`; it is never the implicit default.
2. Smoke-test the token: `admin_helper --env-file bots/<bot>/.env --json me`.
3. If a **full** roster is required, `members-report` needs **Server Members Intent**. If the
   API returns 403, stop, explain the intent, and offer:
   - `members-search <prefix>` for named people
   - `member <user_id>` for a known id
   - `guild` approximate counts + `role-counts`
4. If intent is on:

   ```bash
   ./Skills/admin-helper/scripts/admin_helper --env-file bots/<bot>/.env --guild GUILD_ID \
     members-report --format csv --json
   ```

   Formats: `md` (default), `csv`, `jsonl`. Default path: `reports/admin-helper/<guild>-members-YYYYMMDD.*`.
5. Tell the operator the file path. Files contain user IDs — gitignored; do not commit.
6. Summarize in chat: member count, bots vs humans, pending screening, largest roles (from the
   file or `role-counts`). Do not dump every row into chat unless asked.

## Safety

Read-only. No `--yes`. Do not enable Portal intents unless the user explicitly asked.
