# discord-docs

Portable agent skill for the official **Discord Developers** documentation. Agents read a local
Markdown mirror under `docs/discord/` first, fetch missing/stale pages with a stdlib script, and
only then fall back to the web.

Works with any LLM agent that can read markdown and run shell/Python (Cursor, Claude Code, Codex,
OpenCode, VS Code / Copilot, etc.). Agent instructions: [`SKILL.md`](./SKILL.md).

## File layout

| Path | Audience | Purpose |
|------|----------|---------|
| [`README.md`](./README.md) | Humans | Setup, install, fetch script |
| [`SKILL.md`](./SKILL.md) | LLM agents | Lookup order, cheat sheet, recipes |
| [`index.md`](./index.md) | Agents | Curated topic → official URL → local path |
| [`scripts/fetch_discord_docs.py`](./scripts/fetch_discord_docs.py) | Users & agents | Mirror official `.md` pages into `docs/discord/` |

## Install the skill

From the repo root:

```bash
./Skills/install_skills.sh --auto --skill discord-docs   # non-interactive
./Skills/install_skills.sh                               # wizard (pick skills + IDE)
```

Reload the IDE / agent runtime. In OpenCode invoke **`/discord.docs`**. See
[repo README — Agent Skills](../../README.md#agent-skills-skills).

Alternatives: `@`-reference [`SKILL.md`](./SKILL.md) in chat, or paste skill instructions into
agent context.

## Refresh the local mirror

`docs/discord/` is gitignored (regenerable). Run from the repo root:

```bash
python Skills/discord-docs/scripts/fetch_discord_docs.py            # curated set (index.md)
python Skills/discord-docs/scripts/fetch_discord_docs.py --all      # everything in llms.txt
python Skills/discord-docs/scripts/fetch_discord_docs.py --check    # detect upstream changes
python Skills/discord-docs/scripts/fetch_discord_docs.py interactions/overview  # one slug
```

Any official page works: append `.md` to the URL
(`https://docs.discord.com/developers/<slug>.md`). Full upstream index:
<https://docs.discord.com/llms.txt>.

## See also

- [`SKILL.md`](./SKILL.md) — full agent instructions
- [`index.md`](./index.md) — curated page index
- [`../../README.md`](../../README.md) — repo overview and skill installer
