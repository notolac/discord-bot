---
description: Export a member roster to reports/admin-helper/. Usage: /discord.admin.members-report [guild_id].
---

Load `admin-helper` and follow `Skills/admin-helper/workflows/member_report.md`. Guild from `$ARGUMENTS` or env. Write csv/md/jsonl under `reports/admin-helper/` (gitignored, contains user IDs). Do not commit the file. On 403, explain GUILD_MEMBERS intent; do not enable it without approval.
