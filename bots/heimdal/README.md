# Heimdal — onboarding

Heimdal, the guardian of the bridge, greets new members and lets them in: a persistent
welcome card (rules → `member`), staff-approved claimed roles, cosmetic `/roles`, and an
introduction form. It does **not** moderate (that is [Odin](../odin/README.md)) and does
**not** react to join events on its own (see *Decisions*).

## Commands

| Command | Type | Who | Flow |
|---------|------|-----|------|
| `/welcome [user]` (es: `/bienvenida`) | CHAT_INPUT | Staff (`MANAGE_GUILD`) | No `user`: persistent Components v2 card (`custom_id` `rules_accept`, no target id) plus a claimed-role select. With `user`: targeted card (`rules_accept_<user_id>`) |
| Button `rules_accept` | MESSAGE_COMPONENT | Clicker | Grants **only** `HEIMDAL_MEMBER_ROLE_ID` to `interaction.invoking_user`. Does not edit the public card. Idempotent if they already have `member` |
| Button `rules_accept_<user_id>` | MESSAGE_COMPONENT | Targeted member | Same grant, then `UPDATE_MESSAGE`. Anyone else gets an ephemeral notice |
| `/request-role` (es: `/solicitar-rol`) | CHAT_INPUT | Everyone | Fixed choices `organizer` / `speaker` / `startups` / `enterprises` → evidence modal → card in `HEIMDAL_APPROVAL_CHANNEL_ID` |
| Select `role_ask` | MESSAGE_COMPONENT | Clicker | Same modal as `/request-role`; values are enum keys (`org`/`spk`/`stu`/`ent`), never role snowflakes |
| Buttons `role_ok_<key>_<user_id>` / `role_no_<key>_<user_id>` | MESSAGE_COMPONENT | Staff | Approve: `PUT` the **mapped** role onto the encoded requester. Deny: no `PUT`. Non-staff and forged keys: ephemeral refuse, card unchanged |
| `/roles` | CHAT_INPUT | Everyone | Ephemeral select from `HEIMDAL_INTEREST_ROLES` (cosmetic only; add-only). Unknown values ignored |
| `/introduce` (es: `/presentarme`) | CHAT_INPUT | Everyone | Modal → introduction card in the channel or `HEIMDAL_INTRO_CHANNEL_ID` |

Command payloads: `uv run heimdal list-commands`.

## Role allowlist (security)

Heimdal never `PUT`s a role id that arrived only from the client (select value, modal field, or
a snowflake in `custom_id`). Three maps, all env-driven and filtered at use:

| Map | Used by | May contain |
|-----|---------|-------------|
| Member | `rules_accept` / `rules_accept_<id>` | `HEIMDAL_MEMBER_ROLE_ID` only |
| Approval | Approve button after enum key lookup | organizer, speaker, Startups, Enterprises |
| Interest | `/roles` | Cosmetic ids (PROD: Academia). Overlap with the other maps, approver ids, or the denylist is **dropped** |

`HEIMDAL_DENIED_ROLE_IDS` plus the configured guild ids (`DISCORD_PROD_GUILD_ID` /
`DISCORD_DEV_GUILD_ID` as `@everyone`) are never granted. Approve/Deny additionally requires
the clicker to have `MANAGE_GUILD` (or `ADMINISTRATOR`) on `member.permissions`, **or** a role
in `HEIMDAL_APPROVER_ROLE_IDS`. Missing `member` → refuse. No `/grant-role`.

Official APIs: [Add Guild Member Role](https://docs.discord.com/developers/resources/guild#add-guild-member-role),
[Components](https://docs.discord.com/developers/components/reference),
[command permissions](https://docs.discord.com/developers/interactions/application-commands#permissions),
[permission flags](https://docs.discord.com/developers/topics/permissions).

## Role hierarchy (PROD)

Discord allows `PUT .../roles/{r}` for any role **below** the bot's highest role
([Permission Hierarchy](https://docs.discord.com/developers/topics/permissions#permission-hierarchy)).
Code allowlists remain mandatory even when Discord would 403 a privileged grant.

Observed PROD order (2026-09-06, highest → lowest):

`admin` → `Odin` → **`moderator`** → **`Heimdal`** → `organizer` → `speaker` → `member` →
Academia → Startups → Enterprises

`moderator` sits **above** Heimdal, so Discord itself refuses a `moderator` (or `admin` / Odin)
assignment from this bot. Heimdal **must stay above** `organizer`, `speaker`, `member`, Academia,
Startups and Enterprises, or legitimate grants 403.

New staff-only roles go **above** Heimdal. Do **not** give Heimdal `Administrator`. Do not enable
Gateway or privileged intents unless the operator explicitly asks.

## Permissions / intents

- Installation context: **Guild Install** only. Scopes: `bot`, `applications.commands`.
- Bot permissions: `Send Messages`, `Manage Roles`, `Embed Links`, `View Audit Log`.
- Gateway intents: none — HTTP interactions only.
- To persist the public card in Welcome (`#rules` / `#start-here`), Heimdal needs **Send
  Messages** there (`@everyone` is denied today). **Do not change channel overwrites unless
  the operator says yes** (admin-helper `channel-edit` is destructive). Staff can still run
  `/welcome` in any channel the bot can post in (including `#staff`).

## Variables

See [`.env.example`](.env.example). Shared variables are documented in
[`bots/_template/README.md`](../_template/README.md#variables) (`DISCORD_DEV_GUILD_ID` =
test guild for command sync; `DISCORD_PROD_GUILD_ID` = production guild, same token,
target with `--guild`).

| Variable | Required | Description |
|----------|----------|-------------|
| `HEIMDAL_MEMBER_ROLE_ID` | no | Only role granted on rules acceptance |
| `HEIMDAL_INTEREST_ROLES` | no | Cosmetic `Label:ROLE_ID,...` for `/roles` (max 25). Do not list claimed roles |
| `HEIMDAL_RULES_URL` | no | Link button on the welcome card |
| `HEIMDAL_INTRO_CHANNEL_ID` | no | Channel for introduction cards (default: where the command ran) |
| `HEIMDAL_APPROVAL_CHANNEL_ID` | no | Staff channel for Approve/Deny cards (PROD: `#staff`) |
| `HEIMDAL_APPROVER_ROLE_IDS` | no | Comma-separated ids that may click Approve/Deny (PROD: `admin`,`moderator`) |
| `HEIMDAL_ORGANIZER_ROLE_ID` | no | Approval-only |
| `HEIMDAL_SPEAKER_ROLE_ID` | no | Approval-only |
| `HEIMDAL_STARTUPS_ROLE_ID` | no | Approval-only (not self-serve) |
| `HEIMDAL_ENTERPRISES_ROLE_ID` | no | Approval-only (not self-serve) |
| `HEIMDAL_DENIED_ROLE_IDS` | no | Never grant (admin, moderator, Heimdal, Odin, …) |

## Run

```bash
uv sync
cp bots/heimdal/.env.example bots/heimdal/.env      # fill it
bash bots/heimdal/scripts/smoke-test.sh             # offline self-test
bash bots/heimdal/scripts/sync-commands.sh          # commands → DISCORD_DEV_GUILD_ID
# bash bots/heimdal/scripts/sync-commands.sh --guild <DISCORD_PROD_GUILD_ID>
bash bots/heimdal/scripts/run-dev.sh                # http://127.0.0.1:8000/interactions
bash _shared/scripts/dev-tunnel.sh 8000             # public URL → Developer Portal
uv run pytest bots/heimdal
```

## Layout

```text
src/heimdal/   commands.py · handlers.py · roles.py · settings.py · asgi.py · __main__.py
i18n/          en-US.json (default) · es-ES.json
scripts/       run-dev.sh · sync-commands.sh · smoke-test.sh  (see scripts/README.md)
tests/         pytest
docs/          design notes
logs/ reports/ runtime output (gitignored)
```

## Decisions

- **HTTP interactions, no Gateway.** Automatic greeting on `GUILD_MEMBER_ADD` needs a Gateway
  connection plus the privileged `GUILD_MEMBERS` intent. Persistent `/welcome` card in
  start-here/rules is the self-serve path. Gateway extension remains
  [`tareas/gateway-member-add.md`](../../tareas/gateway-member-add.md).
- **Public accept encodes no user id.** The recipient is always the clicker. Targeted
  `rules_accept_<id>` still requires `clicker == encoded id`.
- **Claimed roles need a human in `#staff`.** Approve buttons are not posted in public
  channels. `custom_id` carries an enum key + requester snowflake, not a role id.
- **Components v2** for cards (`IS_COMPONENTS_V2`), so no `content`/embeds mixing.
  Staff cards set `allowed_mentions` to `parse: []` plus the requester (and staff on resolve).
- **Modal fields use `LABEL` wrappers** (Components v2) instead of action rows. Titles ≤ 45;
  label text ≤ 45; descriptions ≤ 100.
- All user-facing strings live in `i18n/`; English is the default, Spanish via `es-ES`.
- Every `add_member_role` sends `X-Audit-Log-Reason` (e.g. `Heimdal: rules accepted`,
  `Heimdal: approved organizer by <staff_id>`).

## Pending

- [ ] Gateway `GUILD_MEMBER_ADD` auto-welcome (optional extra `heimdal[gateway]`).
- [ ] `/roles` removal of deselected roles (currently add-only).
- [ ] Persist introductions (`reports/`) for `/introduce` re-runs.
- [ ] Operator: grant Heimdal Send Messages on `#start-here` / `#rules` if the public card
      should live there (do not edit overwrites without an explicit yes).
