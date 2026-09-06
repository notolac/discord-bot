---
description: Look up official Discord developer docs via the local mirror, then fetch, then web.
---

Load the `discord-docs` skill (`Skills/discord-docs/SKILL.md`). Answer the Discord API or Developer Portal question in `$ARGUMENTS` using the mandatory lookup order: local `docs/discord/` first, then `python Skills/discord-docs/scripts/fetch_discord_docs.py <slug>`, web last. Cite the page. Never invent endpoints, enums, or limits.
