# discord-bot

Monorepo de bots de Discord en **Python 3.14 + uv**, un bot por carpeta, construidos sobre el
modelo de **HTTP Interactions** de la API oficial (endpoint FastAPI con verificación Ed25519) y
una librería compartida mínima (`discord_core`). Todo el código y la documentación técnica están
en **inglés** (ver [AGENTS.md](AGENTS.md)); este README es la entrada en español.

## Documentos maestros

| Documento | Para qué |
|-----------|----------|
| **[AGENTS.md](AGENTS.md)** | Reglas para agentes LLM (inglés): uv/3.14, secretos, operaciones destructivas, 3 s / deferred, skill de docs |
| **[PLAN-IMPLEMENTACION.md](PLAN-IMPLEMENTACION.md)** | Plan y fases (inglés) |
| **[docs/architecture.md](docs/architecture.md)** | HTTP vs Gateway, `discord_core`, despliegue |
| **[docs/developer-portal.md](docs/developer-portal.md)** | Checklist del Developer Portal: crear app, claves, intents, install link, endpoint |
| **[bots/README.md](bots/README.md)** | Inventario de bots y estado |
| **[_shared/discord_core/README.md](_shared/discord_core/README.md)** | Módulos de la librería compartida |
| **[_shared/scripts/GUIDE.md](_shared/scripts/GUIDE.md)** | Catálogo de scripts |
| **[.cursor/skills/discord-docs/SKILL.md](.cursor/skills/discord-docs/SKILL.md)** | Skill: base de conocimiento de la documentación oficial de Discord (espejo local en `docs/discord/`) |
| **[tareas/](tareas/README.md)** | Trabajo pendiente (despliegue, CI, Gateway, AutoMod, persistencia) |

## Bots

| Bot | Propósito | Carpeta | Estado |
|-----|-----------|---------|--------|
| **Heimdal** | Onboarding: bienvenida con aceptación de reglas, roles de interés, presentación (modal) | [bots/heimdal/](bots/heimdal/README.md) | Base implementada, sin desplegar |
| **Odín** | Moderación: `/warn`, `/timeout`, `/purge` con confirmación, "Report message", "View history", log JSONL | [bots/odin/](bots/odin/README.md) | Base implementada, sin desplegar |
| `_template` | Plantilla para nuevos bots (`/ping`) | [bots/_template/](bots/_template/README.md) | — |

Cada bot es una **aplicación distinta** en el Developer Portal (su propio Application ID y token).

## Estructura del repositorio

```text
discord-bot/
├── README.md                  ← este archivo (español)
├── AGENTS.md                  ← reglas para LLM (inglés)
├── PLAN-IMPLEMENTACION.md
├── pyproject.toml / uv.lock   ← workspace uv (raíz virtual, lista todos los miembros)
├── .python-version            ← 3.14
├── .cursor/
│   ├── rules/discord-bot.mdc  ← recordatorio always-on
│   └── skills/discord-docs/   ← skill + script de espejo de docs oficiales
├── docs/                      ← architecture.md · developer-portal.md · discord/ (espejo, gitignored)
├── _shared/
│   ├── discord_core/          ← librería compartida (src/ + tests/)
│   └── scripts/               ← new-bot.sh · dev-tunnel.sh · GUIDE.md
├── bots/
│   ├── _template/             ← plantilla
│   ├── heimdal/               ← onboarding
│   └── odin/                  ← moderación
└── tareas/                    ← tablero de pendientes
```

Cada bot: `src/<bot>/` · `i18n/` · `scripts/` · `tests/` · `docs/` · `logs/` · `reports/` · `README.md` · `.env.example`.

## Inicio rápido

```bash
uv sync                                          # instala todo el workspace
uv run ruff check . && uv run pytest -q          # calidad (68 tests)
cp bots/heimdal/.env.example bots/heimdal/.env   # rellenar desde el Developer Portal
bash bots/heimdal/scripts/smoke-test.sh          # autotest offline del endpoint
bash bots/heimdal/scripts/sync-commands.sh       # comandos → servidor de pruebas (DISCORD_DEV_GUILD_ID)
bash bots/heimdal/scripts/run-dev.sh             # http://127.0.0.1:8000/interactions
bash _shared/scripts/dev-tunnel.sh 8000          # URL pública → Portal › Interactions Endpoint URL
```

Nuevo bot: `bash _shared/scripts/new-bot.sh thor "Events bot"`.

## Reglas para agentes (resumen humano)

Reglas completas en **[AGENTS.md](AGENTS.md)**:

- Código, comentarios, tests y docs técnicas **solo en inglés**; textos de Discord en `en-US` con traducción `es-ES` en `i18n/`.
- **uv** + Python **3.14**, dependencias pinadas con `==`, un solo `uv.lock`.
- Nunca commitear `.env`, tokens ni claves reales.
- Operaciones destructivas (purge, ban, sync **global** de comandos que borra, cambios en el Portal) requieren **sí explícito**.
- Comandos primero al servidor de pruebas; global solo bajo petición.
- Dudas de la API → skill `discord-docs` (espejo local primero, luego descarga, web al final).
