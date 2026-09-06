# Odin — `/automod` on the AutoMod API

**Status:** open · **Area:** odin

Discord's Auto Moderation resource (`docs/discord/resources/auto-moderation.md`) lets the bot
manage keyword / spam / mention-spam rules **without** the `MESSAGE_CONTENT` intent.

- [ ] Commands: `/automod rule list`, `/automod rule add keyword <words> [action]`, `/automod rule remove <id>` (subcommand group).
- [ ] Client methods: `GET/POST/PATCH/DELETE /guilds/{g}/auto-moderation/rules`.
- [ ] Bot permission `MANAGE_GUILD` for AutoMod endpoints; `default_member_permissions` = `MANAGE_GUILD`.
- [ ] Autocomplete for rule ids.
- [ ] Record changes in the moderation log (`action: "automod"`).
