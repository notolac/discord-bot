---
description: Delete a guild channel (DELETE /channels/{id}). Irreversible. Needs explicit user approval.
---

Load `admin-helper`. Channel id from `$ARGUMENTS`. Warn that guild channel delete cannot be undone (Community Rules/Updates channels cannot be deleted). Only after the user says yes, run `channel-delete <id> --yes` with optional `--reason`.
