---
description: List guild channels (GET /guilds/{id}/channels). Usage: /discord.admin.channels [guild_id].
---

Load `admin-helper`. List channels for the guild in `$ARGUMENTS` (or `DISCORD_GUILD_ID` /
`DISCORD_DEV_GUILD_ID`). Production: `$ARGUMENTS` or `--guild` with `DISCORD_PROD_GUILD_ID`
(never implicit). Run `admin_helper --json channels [guild_id]`. Summarize name, type, id, parent.
This is a read.
