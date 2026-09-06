# Heimdal — design notes

## Onboarding flow

```text
staff: /welcome                  (no user)
  └─ persistent card in the current channel
        [I accept the rules]  custom_id = rules_accept     (no user id)
        [Request a claimed role]  values = org|spk|stu|ent
newbie clicks accept → PUT member role onto clicker → ephemeral ACK (card stays)
newbie selects a claimed role → modal → POST card in HEIMDAL_APPROVAL_CHANNEL_ID
staff: Approve (role_ok_<key>_<user_id>) → staff check → PUT mapped role onto requester
staff: Deny    (role_no_<key>_<user_id>) → staff check → no PUT → card updated

staff: /welcome @newbie          (optional ping)
  └─ targeted card  custom_id = rules_accept_<id>
        └─ only that member; card updates after accept

member: /request-role organizer|speaker|startups|enterprises  → same modal as the select
member: /roles   → cosmetic interest select (allowlist only; add-only)
member: /introduce → modal → card in HEIMDAL_INTRO_CHANNEL_ID
```

## Why the public button encodes no user id

A persistent start-here card cannot bake in a new member's snowflake. The recipient is
always `interaction.invoking_user.id`. Targeted `/welcome @user` still uses
`rules_accept_<user_id>` so other clickers are rejected. `custom_id` max length is 100 chars
([component reference](https://docs.discord.com/developers/components/reference)).

Claimed-role buttons store `org|spk|stu|ent` plus the requester snowflake. The role id is
looked up from env after the key is parsed; unknown keys fail closed with no `PUT`.

## Allowlist and hierarchy

See [README.md](../README.md#role-allowlist-security) and
[README.md](../README.md#role-hierarchy-prod). Discord will allow the bot to grant any role
below it
([Permission Hierarchy](https://docs.discord.com/developers/topics/permissions#permission-hierarchy)).
Observed PROD (2026-09-06): `admin` → Odin → **`moderator`** → **Heimdal** → `organizer` →
`speaker` → `member` → Academia → Startups → Enterprises. Code allowlists + denylist stay
mandatory; Discord hierarchy is the extra brake on `moderator` / `admin`.

Staff gate: `member.permissions` includes `MANAGE_GUILD` (`1 << 5`) or `ADMINISTRATOR`, or
`member.roles` intersects `HEIMDAL_APPROVER_ROLE_IDS`.
`member.permissions` is the channel-total bitfield on the interaction
([Guild Member](https://docs.discord.com/developers/resources/guild#guild-member-object)).

## Error handling

Role assignment failures (`DiscordAPIError`, typically `50013 Missing Permissions` when the
bot role is below the target role, or 403 on a role above the bot) are logged and reported
ephemerally. The staff card is **not** updated on failure, so a retry cannot look like success.

## Official references

- Add member role: https://docs.discord.com/developers/resources/guild#add-guild-member-role
  (local: `docs/discord/resources/guild.md`)
- Components v2 / `custom_id` 1–100: https://docs.discord.com/developers/components/reference
- Modals / LABEL (label ≤ 45, description ≤ 100): https://docs.discord.com/developers/components/using-modal-components
- Command `default_member_permissions`: https://docs.discord.com/developers/interactions/application-commands#permissions
- Permission flags: https://docs.discord.com/developers/topics/permissions
- Allowed mentions: https://docs.discord.com/developers/resources/message#allowed-mentions-object
