# Architecture

## Reception model: HTTP Interactions (default), Gateway (per-bot extension)

Discord delivers interactions to an app in exactly **one** of two ways
([Interactions Overview](https://docs.discord.com/developers/interactions/overview#preparing-for-interactions)):

| | HTTP Interactions Endpoint | Gateway (WebSocket) |
|---|---|---|
| Transport | Discord `POST`s to our public URL | We keep a persistent connection |
| Auth of inbound data | Ed25519 signature headers | Session identify with the bot token |
| Gets | Commands, components, modals, autocomplete | Same + **events** (member join, messages, reactions…) |
| Needs | Public HTTPS URL, answer in 3 s | Long-running process, intents (some privileged) |
| Used by | Every bot in this repo (`discord_core.app`) | Optional `gateway/` module with `discord.py` |

Every bot here runs an HTTP endpoint. When a bot needs events (e.g. Heimdal auto-welcome on
`GUILD_MEMBER_ADD`), it adds a Gateway client **and** moves its interaction handling to
`INTERACTION_CREATE`, because enabling an Interactions Endpoint URL disables Gateway delivery for
that app. Track it in the bot README under *Decisions*.

## Request lifecycle (`discord_core.app`)

```text
Discord ──POST /interactions──▶ FastAPI
   1. verify_signature(PUBLIC_KEY, X-Signature-Ed25519, X-Signature-Timestamp, raw body) → 401 on failure
   2. type == 1 (PING)  → {"type": 1}
   3. Interaction.model_validate(payload)
   4. router.dispatch(interaction, ctx)
        ├─ APPLICATION_COMMAND      → @router.command(name)
        ├─ AUTOCOMPLETE             → @router.autocomplete(name)
        ├─ MESSAGE_COMPONENT        → @router.component(prefix)   (longest prefix wins)
        └─ MODAL_SUBMIT             → @router.modal(prefix)
   5. handler returns a callback payload (responses.*) ──▶ 200 JSON
      defer=True: ACK (type 5 / 6) now, run handler in background,
                  PATCH /webhooks/{app_id}/{token}/messages/@original with the result
```

`InteractionContext` gives handlers `settings`, `client` (`DiscordClient`, outbound REST),
`i18n` (`Localizer`) and `log`.

## Shared library `_shared/discord_core`

Module map and responsibilities: [`_shared/discord_core/README.md`](../_shared/discord_core/README.md).
Design constraints:

- No framework beyond FastAPI + httpx + pydantic; every API shape is traceable to a docs page.
- Builders (`responses.py`) refuse invalid combinations early (Components v2 + `content`,
  modal title > 45, > 25 choices, link button without URL…).
- `commands.sync_commands` always diffs first; global deletions require confirmation.
- Client sets `User-Agent: DiscordBot (<repo>, <version>)`, retries 429 honoring `retry_after`,
  raises `DiscordAPIError(status, code, message, errors)`.

## Per-bot structure

See [`bots/_template/README.md`](../bots/_template/README.md#layout). Bots depend on
`discord-core` through the uv workspace; each has its own Application in the Developer Portal.

## Configuration

`pydantic-settings` reads `.env` in the bot folder (scripts `cd` there) or the process env.
Shared keys (`DISCORD_*`, `HOST`, `PORT`, `LOG_LEVEL`, `DEFAULT_LOCALE`) live in
`discord_core.settings.DiscordSettings`; bot keys are prefixed (`HEIMDAL_*`, `ODIN_*`).

## Logging and reports

`structlog`: console renderer on a TTY, JSON otherwise; JSON lines mirrored to
`bots/<bot>/logs/<bot>.log` (rotating, gitignored). Interaction id/type/command/guild are bound
as context vars per request. Audit data (Odin) goes to `bots/<bot>/reports/*.jsonl`.

## Internationalisation

Code and default strings are English. `Localizer` loads `i18n/<locale>.json`; `ctx.t(key,
interaction)` picks `interaction.locale` with fallback to `en-US`. Command metadata uses
`name_localizations` / `description_localizations` (locale codes from
[Reference › Locales](https://docs.discord.com/developers/reference#locales)).

## Local development loop

```text
uv sync → fill .env → smoke-test.sh → sync-commands.sh (dev guild) → run-dev.sh
→ dev-tunnel.sh (cloudflared/ngrok) → paste <url>/interactions in the Portal → test in the dev server
```

## Deployment (not part of the foundations)

Target: containers (`uv` multi-stage) behind the homelab's Traefik / Cloudflare with a stable
HTTPS URL and `GET /healthz` probes. Discord removes the endpoint URL if it fails its periodic
signature checks, so the service must stay up. Task: [`tareas/deployment.md`](../tareas/deployment.md).
