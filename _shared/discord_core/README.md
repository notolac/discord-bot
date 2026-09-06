# discord-core

Thin shared library used by every bot in this repo. Built directly on the official
Discord API v10 (HTTP interactions model); no large framework.

| Module | Responsibility | Official doc |
|--------|----------------|--------------|
| `security.py` | Ed25519 request verification (`X-Signature-Ed25519` / `X-Signature-Timestamp`) + signing helper for tests | [Interactions Overview](https://docs.discord.com/developers/interactions/overview#validating-security-request-headers) |
| `interactions.py` | Enums (interaction/callback/option/component types, flags) + `pydantic` models for the `Interaction` payload | [Receiving and Responding](https://docs.discord.com/developers/interactions/receiving-and-responding) |
| `responses.py` | Interaction response builders (`message`, `ephemeral`, `deferred`, `update_message`, `modal`, `autocomplete`) + component builders | [Receiving and Responding](https://docs.discord.com/developers/interactions/receiving-and-responding#interaction-response-object) |
| `commands.py` | Typed application command declaration + idempotent sync (diff, then bulk `PUT`) | [Application Commands](https://docs.discord.com/developers/interactions/application-commands) |
| `router.py` | Dispatch by interaction type → command name / `custom_id` prefix; optional deferred execution | — |
| `http.py` | Async `httpx` client: auth header, `User-Agent`, 429 retry, error parsing | [Reference](https://docs.discord.com/developers/reference) |
| `app.py` | FastAPI factory exposing `POST /interactions` and `GET /healthz` | [Interactions Overview](https://docs.discord.com/developers/interactions/overview#preparing-for-interactions) |
| `settings.py` | `pydantic-settings` base settings (`DISCORD_APP_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_BOT_TOKEN`, …) | [Getting Started](https://docs.discord.com/developers/quick-start/getting-started) |
| `logging.py` | `structlog` setup: console/JSON on stdout + rotating file under the bot's `logs/` | — |
| `i18n.py` | Locale string tables (`i18n/<locale>.json`) + helpers for `name_localizations` | [Reference › Locales](https://docs.discord.com/developers/reference#locales) |
| `cli.py` | Shared CLI for bots: `serve`, `sync-commands`, `list-commands`, `smoke` | — |

## Usage from a bot

```python
from discord_core import Router, create_app, run_cli
from discord_core.commands import Command

router = Router()
COMMANDS: list[Command] = [...]


@router.command("ping")
async def ping(interaction, ctx):
    return responses.ephemeral("Pong!")


def main() -> None:
    run_cli(bot_name="mybot", router=router, commands=COMMANDS, settings_cls=MySettings)
```

## Tests

```bash
uv run pytest _shared/discord_core
```
