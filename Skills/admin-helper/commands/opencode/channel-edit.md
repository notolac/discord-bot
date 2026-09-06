---
description: Edit a guild channel (PATCH /channels/{id}). Needs explicit user approval.
---

Load `admin-helper`. Parse `$ARGUMENTS` for channel id and fields (--name --topic --parent --nsfw --position --reason). Confirm the patch in chat. Only after the user says yes, run `channel-edit ... --yes`. MANAGE_CHANNELS required.
