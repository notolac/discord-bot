# Locales — `es-419` and copy review

**Status:** open · **Area:** all bots

Discord picks `name_localizations` / message language by the **user's client locale**. Current
tables: `en-US` (default) and `es-ES`.

- [ ] Add `es-419` to `bots/*/i18n/` and to `name_localizations` in `commands.py` (or derive from `es-ES`).
- [ ] Review `es-ES` copy with a native speaker; keep command names ≤ 32 chars, lowercase.
- [ ] Test that every key in `en-US.json` exists in the other tables (small pytest in `discord_core`).
