# Heimdal — auto-welcome on member join (Gateway)

**Status:** open · **Area:** heimdal

## Why it is not in the base

`GUILD_MEMBER_ADD` is a Gateway event and requires the privileged `GUILD_MEMBERS` intent
(toggle in the Portal for < 100 servers; review above that). Enabling Gateway delivery for the
app also moves interactions to `INTERACTION_CREATE` (HTTP endpoint and Gateway are exclusive).
See `docs/discord/gateway/you-might-not-need-a-privileged-intent.md`.

## Plan

- [ ] Optional extra `heimdal[gateway]` (`discord.py==2.7.1`) — already declared in `pyproject.toml`.
- [ ] `src/heimdal/gateway/` client: on `GUILD_MEMBER_ADD` post the same card `welcome()` builds (reuse the builder, not the handler).
- [ ] Route `INTERACTION_CREATE` through `router.dispatch` and answer via `client.create_interaction_response`.
- [ ] Settings: `HEIMDAL_WELCOME_CHANNEL_ID`, `HEIMDAL_GATEWAY=true`.
- [ ] README *Decisions* update + Portal checklist (intent on, endpoint URL off).
