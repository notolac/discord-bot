---
description: Create a guild channel (POST /guilds/{id}/channels). Needs explicit user approval.
---

Load `admin-helper`. Parse `$ARGUMENTS` for guild, name, type (text/voice/category/announcement/stage/forum), optional parent/topic. Confirm the plan in chat. Only after the user says yes, run `channel-create ... --yes` (optional `--reason`). MANAGE_CHANNELS required. Name 1–100 chars.
