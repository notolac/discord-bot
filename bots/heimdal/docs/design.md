# Heimdal — design notes

## Onboarding flow

```text
staff: /welcome @newbie
  └─ bot: card (Components v2) + [I accept the rules] (custom_id rules_accept_<id>)
        └─ newbie clicks → PUT member role → UPDATE_MESSAGE (card without button)
newbie: /roles  → ephemeral multi-select → roles added → UPDATE_MESSAGE
newbie: /introduce → modal → card posted (channel or HEIMDAL_INTRO_CHANNEL_ID)
```

## Why the button encodes the user id

Discord does not tell the app who a message "belongs to"; the `custom_id` is the only state
available without a database. `rules_accept_<user_id>` lets the handler reject other clickers
and keeps the bot stateless. `custom_id` max length is 100 chars.

## Error handling

Role assignment failures (`DiscordAPIError`, typically `50013 Missing Permissions` when the bot
role is below the target role) are logged and reported to the user ephemerally; the card is not
updated in that case so the member can retry.

## Official references

- Components v2 / `IS_COMPONENTS_V2`: https://docs.discord.com/developers/components/reference
- Add member role: https://docs.discord.com/developers/resources/guild#add-guild-member-role
- Modals: https://docs.discord.com/developers/components/using-modal-components
