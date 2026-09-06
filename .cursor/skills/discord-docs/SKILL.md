---
name: discord-docs
description: >-
  Knowledge base of the official Discord Developers documentation (interactions, application
  commands, components, reference, gateway/intents, permissions, resources). Consults the
  local mirror docs/discord/*.md first and, if missing or stale, downloads the official page
  in .md format with a stdlib script. Use for any question about the Discord API or the
  Developer Portal. Triggers: "discord docs", "documentación de discord", "how do I do X in
  the Discord API", interaction, slash command, callback type, ephemeral, modal, components v2,
  custom_id, snowflake, rate limit, intents, bot permissions, OAuth2 scopes, install link.
---

# Discord docs (official knowledge base)

Answer Discord API questions from the **official documentation only**. Never invent endpoints,
enum values, limits or field names: when unsure, read the page and cite it.

## Lookup order (mandatory)

1. **Local mirror:** `docs/discord/<slug>.md` (repo root). Find the slug in [index.md](index.md).
   Example: interactions overview → `docs/discord/interactions/overview.md`.
2. **Missing or possibly stale** (`docs/discord/_SOURCE.md` older than ~30 days, or the topic is
   not mirrored): run from the repo root

   ```bash
   python .cursor/skills/discord-docs/scripts/fetch_discord_docs.py                 # curated set (index.md)
   python .cursor/skills/discord-docs/scripts/fetch_discord_docs.py resources/guild # one slug
   python .cursor/skills/discord-docs/scripts/fetch_discord_docs.py --all           # everything in llms.txt
   python .cursor/skills/discord-docs/scripts/fetch_discord_docs.py --check         # detect upstream changes
   ```

   Any page works: take the official URL and append `.md`
   (`https://docs.discord.com/developers/<slug>.md`). Full upstream index: `https://docs.discord.com/llms.txt`.
3. **Web search** only if steps 1–2 cannot answer (e.g. behaviour not documented). Say so explicitly.

`docs/discord/` is gitignored (regenerable). Do not edit mirrored files by hand.

## Constants cheat sheet (verified against the mirror; re-check on doubt)

| Concept | Values |
|---------|--------|
| Interaction `type` | 1 PING · 2 APPLICATION_COMMAND · 3 MESSAGE_COMPONENT · 4 APPLICATION_COMMAND_AUTOCOMPLETE · 5 MODAL_SUBMIT |
| Callback `type` | 1 PONG · 4 CHANNEL_MESSAGE_WITH_SOURCE · 5 DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE · 6 DEFERRED_UPDATE_MESSAGE* · 7 UPDATE_MESSAGE* · 8 AUTOCOMPLETE_RESULT · 9 MODAL · 12 LAUNCH_ACTIVITY (*components only) |
| Message flags on responses | `EPHEMERAL` = 64 (1<<6) · `IS_COMPONENTS_V2` = 32768 (1<<15) · `SUPPRESS_EMBEDS` = 4 · `SUPPRESS_NOTIFICATIONS` = 4096 |
| Command `type` | 1 CHAT_INPUT · 2 USER · 3 MESSAGE · 4 PRIMARY_ENTRY_POINT |
| Option `type` | 1 SUB_COMMAND · 2 SUB_COMMAND_GROUP · 3 STRING · 4 INTEGER · 5 BOOLEAN · 6 USER · 7 CHANNEL · 8 ROLE · 9 MENTIONABLE · 10 NUMBER · 11 ATTACHMENT |
| Interaction context | 0 GUILD · 1 BOT_DM · 2 PRIVATE_CHANNEL — installation context: 0 GUILD_INSTALL · 1 USER_INSTALL |
| Deadlines | initial response **3 s**; interaction token valid **15 min** (follow-ups / edits) |
| Limits | 100 global CHAT_INPUT, 15 USER, 15 MESSAGE commands; 25 options; 25 choices; 200 command creates/guild/day; 5 follow-ups for user-installed-only apps |
| Names | CHAT_INPUT names: 1–32 chars, lowercase; descriptions 1–100; USER/MESSAGE description must be empty |
| HTTP | base `https://discord.com/api/v10` · `Authorization: Bot <token>` · `User-Agent: DiscordBot ($url, $version)` · `Content-Type: application/json` · 429 → wait `retry_after` |
| Signature | headers `X-Signature-Ed25519`, `X-Signature-Timestamp`; verify `timestamp + raw_body`; return **401** on failure |
| Permissions bits (subset) | MANAGE_GUILD 1<<5 · MANAGE_MESSAGES 1<<13 · MANAGE_ROLES 1<<28 · MODERATE_MEMBERS 1<<40 · `default_member_permissions` is a **string**; `"0"` = admins only |

## Recipes (each maps to code in `_shared/discord_core`)

| Need | Do | Source section |
|------|----|----------------|
| Verify a request (Python) | `VerifyKey(bytes.fromhex(PUBLIC_KEY)).verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))`, catch `BadSignatureError` → 401 | interactions/overview § Validating Security Request Headers · `security.py` |
| Answer PING | body `{"type":1}` → respond `200 {"type":1}` | interactions/overview § Responding to PING Requests |
| Register commands for testing | `PUT /applications/{app_id}/guilds/{guild_id}/commands` (instant) — global `PUT` is cached and **deletes** commands not in the list | application-commands § Registering a Command · `commands.py` |
| Long work | reply type 5 (or 6 for components) within 3 s, then `PATCH /webhooks/{app_id}/{token}/messages/@original` | receiving-and-responding § Followup Messages · `router.py` (`defer=True`) |
| Ephemeral reply | callback 4 with `data.flags = 64` | receiving-and-responding § Interaction Callback Data |
| Components v2 message | set flag 32768, use `TEXT_DISPLAY`(10)/`CONTAINER`(17)/`SECTION`(9)…, **no** `content`/`embeds` | components/reference · `responses.py` |
| Modal | callback 9 with `custom_id`, `title` ≤ 45, 1–5 components (`LABEL` 18 wrapping `TEXT_INPUT` 4) | components/using-modal-components |
| Context-menu command | command `type` 2/3; interaction has `data.target_id` and `data.resolved.users` / `.messages` | application-commands § User/Message Commands |
| Restrict a command | `default_member_permissions` (string bitfield) + `contexts` `[0]` for guild-only | application-commands § Permissions |
| Localize | `name_localizations` / `description_localizations` with locale keys (`es-ES`, `en-US`…) | reference § Locales · `i18n.py` |
| Mention safely | always send `allowed_mentions` (`{"parse":[]}` or explicit `users`) | reference § Message Formatting |
| Timeout a member | `PATCH /guilds/{g}/members/{u}` `{"communication_disabled_until": ISO8601}` (≤ 28 days) | resources/guild § Modify Guild Member |
| Bulk delete | `POST /channels/{c}/messages/bulk-delete` 2–100 ids, < 14 days old | resources/message § Bulk Delete Messages |

## Answer format

1. Short answer (what to send / call, with exact values).
2. Citation: `docs.discord.com/developers/<slug>#<section>` and the local path read.
3. If the repo already implements it, point to the module (`_shared/discord_core/...`).
4. If step 3 (web) was needed, state that the official docs did not cover it.

## Repo conventions that interact with the docs

- Guild commands first; global sync needs `--yes` when it deletes (see `AGENTS.md`).
- Handlers must answer in 3 s or use `defer=True`.
- One Application ID per bot; never share tokens.
- English-only code and technical docs; Discord-facing strings default `en-US`, Spanish via `es-ES` tables.
