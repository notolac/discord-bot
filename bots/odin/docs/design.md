# Odin — design notes

## Purge flow (deferred component)

```text
mod: /purge 25
  └─ bot: ephemeral "Delete the last 25 messages?" [Delete 25] [Cancel]
       ├─ Cancel  → UPDATE_MESSAGE (7) "Purge cancelled."
       └─ Delete  → DEFERRED_UPDATE_MESSAGE (6)          ← within 3 s
                     background: GET /channels/{c}/messages?limit=25
                                 POST /channels/{c}/messages/bulk-delete
                                 PATCH /webhooks/{app}/{token}/messages/@original  ← result
```

`bulk-delete` requires 2–100 ids and refuses messages older than 14 days, so the handler
filters by `timestamp` and falls back to a single `DELETE` when only one id remains.

## Why context-menu commands

`Report message` and `View history` are `MESSAGE` / `USER` commands: Discord sends
`data.target_id` plus the `resolved` object, so the bot gets the message content/author without
the privileged `MESSAGE_CONTENT` intent and without any Gateway connection.

## Official references

- Modify guild member (`communication_disabled_until`): https://docs.discord.com/developers/resources/guild#modify-guild-member
- Bulk delete: https://docs.discord.com/developers/resources/message#bulk-delete-messages
- Context-menu commands: https://docs.discord.com/developers/interactions/application-commands#message-commands
- Timestamp markdown `<t:unix:R>`: https://docs.discord.com/developers/reference#message-formatting
