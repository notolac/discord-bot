# Heimdal — onboarding

Heimdal, the guardian of the bridge, greets new members and lets them in: welcome card with
rules acceptance, self-assignable interest roles and an introduction form. It does **not**
moderate (that is [Odin](../odin/README.md)) and does **not** react to join events on its own
(see *Decisions*).

## Commands

| Command | Type | Who | Flow |
|---------|------|-----|------|
| `/welcome [user]` (es: `/bienvenida`) | CHAT_INPUT | Staff (`MANAGE_GUILD`) | Posts a Components v2 card mentioning the member with an **I accept the rules** button (`rules_accept_<user_id>`) and an optional link to the rules |
| Button `rules_accept_<user_id>` | MESSAGE_COMPONENT | The targeted member | Grants `HEIMDAL_MEMBER_ROLE_ID` via `PUT /guilds/{g}/members/{u}/roles/{r}` and updates the card (`UPDATE_MESSAGE`). Anyone else gets an ephemeral notice |
| `/roles` | CHAT_INPUT | Everyone | Ephemeral multi-select (`roles_pick`) built from `HEIMDAL_INTEREST_ROLES`; selected roles are added |
| `/introduce` (es: `/presentarme`) | CHAT_INPUT | Everyone | Opens a modal (`introduce_modal`: name, about, interests). On submit posts an introduction card in the channel or in `HEIMDAL_INTRO_CHANNEL_ID` |

Command payloads: `uv run heimdal list-commands`.

## Permissions / intents

- Installation context: **Guild Install** only. Scopes: `bot`, `applications.commands`.
- Bot permissions: `Send Messages`, `Manage Roles`, `Embed Links`. The bot's highest role must
  be **above** every role it assigns.
- Gateway intents: none — HTTP interactions only.

## Variables

See [`.env.example`](.env.example). Shared variables are documented in
[`bots/_template/README.md`](../_template/README.md#variables) (`DISCORD_DEV_GUILD_ID` =
test guild for command sync; `DISCORD_PROD_GUILD_ID` = production guild, same token,
target with `--guild`).

| Variable | Required | Description |
|----------|----------|-------------|
| `HEIMDAL_MEMBER_ROLE_ID` | no | Role granted on rules acceptance; if empty the button only updates the card |
| `HEIMDAL_INTEREST_ROLES` | no | `Label:ROLE_ID,...` shown by `/roles` (max 25) |
| `HEIMDAL_RULES_URL` | no | Adds a link button to the welcome card |
| `HEIMDAL_INTRO_CHANNEL_ID` | no | Channel for introduction cards (default: where the command ran) |

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
src/heimdal/   commands.py · handlers.py · settings.py · __main__.py
i18n/          en-US.json (default) · es-ES.json
scripts/       run-dev.sh · sync-commands.sh · smoke-test.sh  (see scripts/README.md)
tests/         pytest
docs/          design notes
logs/ reports/ runtime output (gitignored)
```

## Decisions

- **HTTP interactions, no Gateway.** Automatic greeting on `GUILD_MEMBER_ADD` needs a Gateway
  connection plus the privileged `GUILD_MEMBERS` intent. Alternative used here: Discord's native
  Server Onboarding for the first screen, then staff runs `/welcome`. Gateway extension is an
  open task: [`tareas/gateway-member-add.md`](../../tareas/gateway-member-add.md).
- **Components v2** for cards (`IS_COMPONENTS_V2`), so no `content`/embeds mixing.
- **Modal fields use `LABEL` wrappers** (Components v2) instead of action rows.
- All user-facing strings live in `i18n/`; English is the default, Spanish via `es-ES`.

## Pending

- [ ] Gateway `GUILD_MEMBER_ADD` auto-welcome (optional extra `heimdal[gateway]`).
- [ ] `/roles` removal of deselected roles (currently add-only).
- [ ] Persist introductions (`reports/`) for `/introduce` re-runs.
