# Developer Portal checklist (per bot)

Source: [Building your first Discord Bot](https://docs.discord.com/developers/quick-start/getting-started)
(mirror: `docs/discord/quick-start/getting-started.md`). One Application per bot.

## 1. Create the application

1. <https://discord.com/developers/applications> → **New Application** → name (`Heimdal`, `Odin`…).
2. **General Information**: copy **Application ID** → `DISCORD_APP_ID`; copy **Public Key** → `DISCORD_PUBLIC_KEY`.
3. **Bot** page → **Reset Token** → copy once → `DISCORD_BOT_TOKEN`. Store it in a password manager;
   it is never shown again. Never commit it.

## 2. Bot settings

- **Privileged Gateway Intents**: leave all **off** for HTTP-only bots (this repo's default).
  Turn on `Server Members Intent` only for a Gateway extension that needs `GUILD_MEMBER_ADD`
  (Heimdal task). `Message Content Intent` is not required by any current command.
- **Public Bot**: off while developing.

## 3. Installation

- **Installation Contexts**: `Guild Install` ✔ (both Heimdal and Odin). `User Install` off unless the
  bot has user-context commands.
- **Install Link**: *Discord Provided Link*.
- **Default Install Settings › Guild Install**: scopes `applications.commands` + `bot`; bot
  permissions per bot README:
  - Heimdal: Send Messages, Manage Roles, Embed Links.
  - Odin: Send Messages, Moderate Members, Manage Messages, Read Message History.
- Open the install link → **Add to server** → pick the **test server** first
  (`DISCORD_DEV_GUILD_ID` = that server id; enable Developer Mode in Discord to copy ids).
  Invite the **same** application to the production server and store that id as
  `DISCORD_PROD_GUILD_ID`. One token covers both guilds; command sync and admin-helper
  default to the dev guild unless you pass `--guild`.

## 4. Register commands

```bash
cp bots/<bot>/.env.example bots/<bot>/.env   # fill DISCORD_* (APP_ID, PUBLIC_KEY, TOKEN, DEV/PROD guild ids)
bash bots/<bot>/scripts/sync-commands.sh     # → DISCORD_DEV_GUILD_ID, prints the diff
# bash bots/<bot>/scripts/sync-commands.sh --guild <DISCORD_PROD_GUILD_ID>
```

Guild commands appear immediately. Global (`--global --yes`) only when the bot is ready for
production; global propagation is cached.

## 5. Interactions Endpoint URL

1. `bash bots/<bot>/scripts/run-dev.sh` (port from `.env`).
2. `bash _shared/scripts/dev-tunnel.sh <port>` → public `https://…` URL.
3. **General Information › Interactions Endpoint URL** = `<public-url>/interactions` → **Save**.
   Discord sends a `PING` and invalid-signature probes; the save succeeds only if the server
   answers `{"type":1}` and 401 respectively (`smoke-test.sh` checks the same offline).
4. Use a command in the test server; watch the JSON logs in the terminal / `bots/<bot>/logs/`.

Discord re-validates the endpoint periodically; if it fails, the URL is removed and you get an
email + system DM. A stable deployment is tracked in [`tareas/deployment.md`](../tareas/deployment.md).

## 6. Role hierarchy (Heimdal / Odin)

The bot's own role must sit **above** any role it assigns (`Manage Roles`) or any member it times
out (`Moderate Members`). Otherwise the API returns `50013 Missing Permissions`, which the bots
report ephemerally.

Heimdal must also sit **below** roles it must never grant (`admin`, `moderator`, other bots).
PROD order (2026-09-06): `admin` → Odin → `moderator` → Heimdal → `organizer` → `speaker` →
`member` → Academia → Startups → Enterprises. Details:
[bots/heimdal/README.md](../bots/heimdal/README.md#role-hierarchy-prod).

## 7. Rotation

If a token or public key changes: update `.env`, restart the bot, and re-save the endpoint URL if
the public key changed. Rotation is a destructive change — confirm with the owner first.
