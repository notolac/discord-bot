# Odin — replace JSONL audit log with a database

**Status:** open · **Area:** odin

`odin.services.report_log.ReportLog` is an append-only JSONL file per guild. Fine for one
process; not for multiple replicas or queries beyond "last N for a user".

- [ ] Pick SQLite (single replica, volume) vs Postgres (homelab already runs it).
- [ ] Keep `ModerationRecord` as the domain model; add a `ReportStore` protocol with JSONL and DB implementations.
- [ ] Migration script `scripts/import-jsonl.py`.
- [ ] Retention policy + `/history` pagination.
