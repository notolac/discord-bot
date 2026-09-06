# reports/

Local-only outputs that may contain Discord **user IDs** and guild metadata.

| Path | Source | Git |
|------|--------|-----|
| `reports/admin-helper/` | `admin-helper` skill (`members-report`) | Ignored (`**/reports/*`) |
| `bots/<bot>/reports/` | That bot's audit logs / scripts | Ignored except `.gitkeep` / `README.md` |

Do not commit these files. Retention: delete files older than **90 days** unless a task says
otherwise. The owner may delete this directory at any time (destructive — confirm first).
