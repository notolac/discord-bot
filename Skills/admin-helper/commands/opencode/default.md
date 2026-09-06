---
description: Guild admin via Discord REST (members, channels, reports). Usage: /discord.admin [request].
---

Load the `admin-helper` skill (`Skills/admin-helper/SKILL.md`). Handle the guild-admin request in `$ARGUMENTS`. If none, list CLI commands and which ones need `--yes`. Use `./Skills/admin-helper/scripts/admin_helper` with `--env-file` and `--json`. Never invent Discord endpoints; use `discord-docs` for anything the CLI does not wrap. Do not pass `--yes` unless the user already approved a write in this chat.
