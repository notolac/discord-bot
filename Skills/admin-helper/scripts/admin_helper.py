#!/usr/bin/env python3
"""Discord guild administration CLI for the admin-helper skill.

Stdlib-only. Talks to Discord HTTP API v10 with a bot token so operators (and AI
agents) can list members, export reports, and create/edit/delete channels.

Requires Python >= 3.10 (repo standard: 3.14 via uv). Prefer the wrapper:

    ./Skills/admin-helper/scripts/admin_helper <command> [args]
    uv run --python 3.14 Skills/admin-helper/scripts/admin_helper.py <command> [args]

Credentials:
    DISCORD_BOT_TOKEN     bot token (required)
    DISCORD_GUILD_ID      default guild (optional)
    DISCORD_DEV_GUILD_ID  fallback default guild (optional)
    --env-file PATH       load KEY=VALUE from a bot ``.env`` (does not override
                          variables already set in the environment)

Write commands require interactive confirmation, or ``--yes`` only after the
user explicitly approved the action in chat.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

API_BASE = "https://discord.com/api/v10"
REPO_URL = "https://github.com/notolac/discord-bot"
USER_AGENT = f"DiscordBot ({REPO_URL}, admin-helper)"
MAX_RETRIES = 3
MEMBERS_PAGE_MAX = 1000
MEMBERS_DEFAULT_CAP = 10_000
AUDIT_LIMIT_MAX = 100
CHANNEL_NAME_MAX = 100
REASON_MAX = 512

# docs.discord.com/developers/resources/channel#channel-object-channel-types
CHANNEL_TYPES: dict[str, int] = {
    "text": 0,
    "voice": 2,
    "category": 4,
    "announcement": 5,
    "stage": 13,
    "forum": 15,
    "media": 16,
}
CHANNEL_TYPE_NAMES: dict[int, str] = {value: name for name, value in CHANNEL_TYPES.items()}
CHANNEL_TYPE_NAMES.update(
    {
        1: "dm",
        3: "group_dm",
        10: "announcement_thread",
        11: "public_thread",
        12: "private_thread",
        14: "directory",
    }
)

INTENT_HINT = (
    "List Guild Members requires the GUILD_MEMBERS privileged intent "
    "(Developer Portal → Bot → Privileged Gateway Intents → Server Members Intent). "
    "Without it, use members-search, member <user_id>, guild --with-counts, or role-counts. "
    "See docs.discord.com/developers/resources/guild#list-guild-members "
    "and gateway/you-might-not-need-a-privileged-intent."
)


class AdminAPIError(Exception):
    """Non-2xx response from the Discord API."""

    def __init__(self, status: int, body: Any, *, method: str, path: str) -> None:
        self.status = status
        self.body = body
        self.method = method
        self.path = path
        self.code: int | None = body.get("code") if isinstance(body, dict) else None
        self.message: str = body.get("message", "") if isinstance(body, dict) else str(body)[:200]
        super().__init__(f"{method} {path} -> {status} {self.code}: {self.message}")


def die(message: str, code: int = 1) -> NoReturn:
    """Print an error to stderr and exit."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def repo_root() -> Path:
    """Walk up until ``pyproject.toml`` + ``bots/`` (workspace root)."""
    start = Path(__file__).resolve().parent
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file() and (candidate / "bots").is_dir():
            return candidate
    die(f"could not find repo root from {start}")


def default_reports_dir() -> Path:
    """Gitignored report directory at the repo root."""
    return repo_root() / "reports" / "admin-helper"


def redact(text: str, token: str) -> str:
    """Strip the bot token from error text before printing."""
    if token:
        text = text.replace(token, "***")
    return text


def load_env_file(path: Path) -> None:
    """Load ``KEY=VALUE`` lines into ``os.environ`` without overriding existing keys."""
    if not path.is_file():
        die(f"env file not found: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def require_token() -> str:
    """Return ``DISCORD_BOT_TOKEN`` or exit."""
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        die("Set DISCORD_BOT_TOKEN (or pass --env-file bots/<bot>/.env). Never commit tokens.")
    return token


def resolve_guild(cli_guild: str | None, positional: str | None = None) -> str:
    """Resolve guild id: positional → ``--guild`` → env defaults."""
    for candidate in (
        positional,
        cli_guild,
        os.environ.get("DISCORD_GUILD_ID", "").strip() or None,
        os.environ.get("DISCORD_DEV_GUILD_ID", "").strip() or None,
    ):
        if candidate:
            return candidate
    die(
        "missing guild id: pass it as an argument, --guild, DISCORD_GUILD_ID, or DISCORD_DEV_GUILD_ID"
    )


def confirm_write(prompt: str, *, yes: bool) -> None:
    """Require explicit confirmation before Discord write ops.

    Agents: get chat approval first, then pass ``--yes``.
    Interactive operators: type ``yes`` at the prompt.
    """
    if yes:
        return
    print(prompt, file=sys.stderr)
    if not sys.stdin.isatty():
        die(
            "confirmation required in non-interactive mode; "
            "pass --yes only after explicit user approval"
        )
    try:
        answer = input("Type 'yes' to proceed: ").strip().lower()
    except EOFError:
        die("confirmation required; pass --yes only after explicit user approval")
    if answer != "yes":
        die("aborted")


def parse_channel_type(value: str) -> int:
    """Map a name or integer to a channel type id."""
    lowered = value.strip().lower()
    if lowered in CHANNEL_TYPES:
        return CHANNEL_TYPES[lowered]
    if lowered.isdigit():
        return int(lowered)
    die(f"unknown channel type {value!r}; use {', '.join(sorted(CHANNEL_TYPES))} or an integer id")


def channel_type_label(type_id: int) -> str:
    """Human label for a channel type id."""
    return CHANNEL_TYPE_NAMES.get(type_id, str(type_id))


def _decode_body(raw: bytes) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def request(
    method: str,
    path: str,
    token: str,
    *,
    payload: dict[str, Any] | list[Any] | None = None,
    params: dict[str, Any] | None = None,
    reason: str | None = None,
) -> Any:
    """Perform a Discord API request, retrying HTTP 429."""
    query = ""
    if params:
        filtered = {key: str(value) for key, value in params.items() if value is not None}
        if filtered:
            query = "?" + urllib.parse.urlencode(filtered)
    url = f"{API_BASE}{path}{query}"
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json",
    }
    if reason:
        encoded = urllib.parse.quote(reason[:REASON_MAX], safe="")
        headers["X-Audit-Log-Reason"] = encoded
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return _decode_body(response.read())
        except urllib.error.HTTPError as exc:
            body = _decode_body(exc.read())
            if exc.code == 429 and attempt < MAX_RETRIES:
                attempt += 1
                retry_after = 1.0
                if isinstance(body, dict) and "retry_after" in body:
                    try:
                        retry_after = float(body["retry_after"])
                    except TypeError, ValueError:
                        retry_after = 1.0
                time.sleep(retry_after)
                continue
            error = AdminAPIError(exc.code, body, method=method, path=path)
            message = redact(str(error), token)
            if exc.code in {401, 403} and path.endswith("/members") and method == "GET":
                message = f"{message}\n{INTENT_HINT}"
            die(message)
        except urllib.error.URLError as exc:
            die(redact(f"network error: {exc}", token))


def emit(data: Any, *, as_json: bool, rows: list[dict[str, Any]] | None = None) -> None:
    """Print JSON or a compact table to stdout."""
    if as_json or rows is None:
        json.dump(
            data if as_json or rows is None else rows, sys.stdout, indent=2, ensure_ascii=False
        )
        sys.stdout.write("\n")
        return
    if not rows:
        print("(none)")
        return
    keys = list(rows[0].keys())
    widths = {key: len(key) for key in keys}
    for row in rows:
        for key in keys:
            widths[key] = max(widths[key], len(str(row.get(key, ""))))
    print("  ".join(key.ljust(widths[key]) for key in keys))
    print("  ".join("-" * widths[key] for key in keys))
    for row in rows:
        print("  ".join(str(row.get(key, "")).ljust(widths[key]) for key in keys))


def user_summary(user: dict[str, Any] | None) -> dict[str, Any]:
    """Flatten a user object for tables and reports."""
    user = user or {}
    return {
        "id": user.get("id", ""),
        "username": user.get("username", ""),
        "global_name": user.get("global_name") or "",
        "bot": bool(user.get("bot")),
    }


def member_row(member: dict[str, Any], role_names: dict[str, str] | None = None) -> dict[str, Any]:
    """Flatten a guild member object."""
    user = user_summary(member.get("user") if isinstance(member.get("user"), dict) else {})
    role_ids = [str(role_id) for role_id in member.get("roles") or []]
    if role_names:
        roles = ";".join(role_names.get(role_id, role_id) for role_id in role_ids)
    else:
        roles = ";".join(role_ids)
    return {
        "user_id": user["id"],
        "username": user["username"],
        "global_name": user["global_name"],
        "nick": member.get("nick") or "",
        "bot": user["bot"],
        "pending": bool(member.get("pending")),
        "joined_at": member.get("joined_at") or "",
        "roles": roles,
    }


def channel_row(channel: dict[str, Any]) -> dict[str, Any]:
    """Flatten a channel object."""
    return {
        "id": channel.get("id", ""),
        "type": channel_type_label(int(channel.get("type", -1))),
        "name": channel.get("name") or "",
        "parent_id": channel.get("parent_id") or "",
        "position": channel.get("position", ""),
        "topic": (channel.get("topic") or "")[:60],
    }


def guild_row(guild: dict[str, Any]) -> dict[str, Any]:
    """Flatten a (partial) guild object."""
    return {
        "id": guild.get("id", ""),
        "name": guild.get("name", ""),
        "owner": guild.get("owner", ""),
        "approximate_member_count": guild.get("approximate_member_count", ""),
        "permissions": guild.get("permissions", ""),
    }


def list_members(token: str, guild_id: str, *, cap: int) -> list[dict[str, Any]]:
    """Paginate ``GET /guilds/{guild.id}/members`` (limit 1–1000, ``after`` cursor)."""
    members: list[dict[str, Any]] = []
    after = "0"
    remaining = cap
    while remaining > 0:
        page_size = min(MEMBERS_PAGE_MAX, remaining)
        page = request(
            "GET",
            f"/guilds/{guild_id}/members",
            token,
            params={"limit": page_size, "after": after},
        )
        if not isinstance(page, list) or not page:
            break
        members.extend(page)
        remaining -= len(page)
        last = page[-1]
        user = last.get("user") if isinstance(last, dict) else None
        user_id = user.get("id") if isinstance(user, dict) else None
        if not user_id or len(page) < page_size:
            break
        after = str(user_id)
    return members


def role_name_map(token: str, guild_id: str) -> dict[str, str]:
    """Map role id → name via ``GET /guilds/{guild.id}/roles``."""
    roles = request("GET", f"/guilds/{guild_id}/roles", token)
    if not isinstance(roles, list):
        return {}
    return {
        str(role.get("id")): str(role.get("name", "")) for role in roles if isinstance(role, dict)
    }


def cmd_me(token: str, as_json: bool) -> None:
    """``GET /users/@me``."""
    data = request("GET", "/users/@me", token)
    row = user_summary(data if isinstance(data, dict) else {})
    emit(data, as_json=as_json, rows=[row])


def cmd_guilds(token: str, as_json: bool) -> None:
    """``GET /users/@me/guilds`` with counts."""
    data = request("GET", "/users/@me/guilds", token, params={"with_counts": "true", "limit": 200})
    rows = [guild_row(item) for item in data] if isinstance(data, list) else []
    emit(data, as_json=as_json, rows=rows)


def cmd_guild(token: str, guild_id: str, as_json: bool) -> None:
    """``GET /guilds/{guild.id}?with_counts=true``."""
    data = request("GET", f"/guilds/{guild_id}", token, params={"with_counts": "true"})
    row = {
        "id": data.get("id", "") if isinstance(data, dict) else "",
        "name": data.get("name", "") if isinstance(data, dict) else "",
        "owner_id": data.get("owner_id", "") if isinstance(data, dict) else "",
        "approximate_member_count": data.get("approximate_member_count", "")
        if isinstance(data, dict)
        else "",
        "approximate_presence_count": data.get("approximate_presence_count", "")
        if isinstance(data, dict)
        else "",
    }
    emit(data, as_json=as_json, rows=[row])


def cmd_channels(token: str, guild_id: str, as_json: bool) -> None:
    """``GET /guilds/{guild.id}/channels`` (no threads)."""
    data = request("GET", f"/guilds/{guild_id}/channels", token)
    rows = [channel_row(item) for item in data] if isinstance(data, list) else []
    rows.sort(key=lambda row: (str(row["parent_id"]), str(row["position"]), str(row["name"])))
    emit(data, as_json=as_json, rows=rows)


def cmd_channel(token: str, channel_id: str, as_json: bool) -> None:
    """``GET /channels/{channel.id}``."""
    data = request("GET", f"/channels/{channel_id}", token)
    emit(data, as_json=as_json, rows=[channel_row(data)] if isinstance(data, dict) else [])


def cmd_roles(token: str, guild_id: str, as_json: bool) -> None:
    """``GET /guilds/{guild.id}/roles``."""
    data = request("GET", f"/guilds/{guild_id}/roles", token)
    rows = []
    if isinstance(data, list):
        for role in data:
            if isinstance(role, dict):
                rows.append(
                    {
                        "id": role.get("id", ""),
                        "name": role.get("name", ""),
                        "position": role.get("position", ""),
                        "managed": role.get("managed", ""),
                        "permissions": role.get("permissions", ""),
                    }
                )
        rows.sort(key=lambda row: int(row["position"] or 0), reverse=True)
    emit(data, as_json=as_json, rows=rows)


def cmd_role_counts(token: str, guild_id: str, as_json: bool) -> None:
    """``GET /guilds/{guild.id}/roles/member-counts`` (no @everyone)."""
    data = request("GET", f"/guilds/{guild_id}/roles/member-counts", token)
    names = role_name_map(token, guild_id)
    rows = []
    if isinstance(data, dict):
        for role_id, count in data.items():
            rows.append({"role_id": role_id, "name": names.get(str(role_id), ""), "count": count})
        rows.sort(key=lambda row: int(row["count"] or 0), reverse=True)
    emit(data, as_json=as_json, rows=rows)


def cmd_member(token: str, guild_id: str, user_id: str, as_json: bool) -> None:
    """``GET /guilds/{guild.id}/members/{user.id}``."""
    data = request("GET", f"/guilds/{guild_id}/members/{user_id}", token)
    names = role_name_map(token, guild_id)
    rows = [member_row(data, names)] if isinstance(data, dict) else []
    emit(data, as_json=as_json, rows=rows)


def cmd_members(token: str, guild_id: str, as_json: bool, cap: int) -> None:
    """Paginated list of guild members."""
    members = list_members(token, guild_id, cap=cap)
    names = role_name_map(token, guild_id)
    rows = [member_row(item, names) for item in members if isinstance(item, dict)]
    emit(members if as_json else rows, as_json=as_json, rows=None if as_json else rows)


def cmd_members_search(token: str, guild_id: str, query: str, as_json: bool, limit: int) -> None:
    """``GET /guilds/{guild.id}/members/search`` (no privileged intent)."""
    data = request(
        "GET",
        f"/guilds/{guild_id}/members/search",
        token,
        params={"query": query, "limit": max(1, min(limit, MEMBERS_PAGE_MAX))},
    )
    names = role_name_map(token, guild_id)
    rows = [member_row(item, names) for item in data] if isinstance(data, list) else []
    emit(data, as_json=as_json, rows=rows)


def _write_report(
    rows: list[dict[str, Any]],
    path: Path,
    fmt: str,
    *,
    guild_id: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "jsonl":
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return
    if fmt == "csv":
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=list(rows[0].keys()) if rows else ["user_id"]
            )
            writer.writeheader()
            writer.writerows(rows)
        return
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Member report — guild `{guild_id}`",
        "",
        f"Generated: **{now}** · members: **{len(rows)}**.",
        "Contains Discord user IDs. Do not commit. Retention: see `reports/README.md`.",
        "",
        "| user_id | username | global_name | nick | bot | pending | joined_at | roles |",
        "|---------|----------|-------------|------|-----|---------|-----------|-------|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(row.get(key, "")).replace("|", "\\|")
                for key in (
                    "user_id",
                    "username",
                    "global_name",
                    "nick",
                    "bot",
                    "pending",
                    "joined_at",
                    "roles",
                )
            )
            + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_members_report(
    token: str,
    guild_id: str,
    as_json: bool,
    *,
    cap: int,
    fmt: str,
    out: Path | None,
) -> None:
    """Export members to a gitignored report file (user IDs)."""
    members = list_members(token, guild_id, cap=cap)
    names = role_name_map(token, guild_id)
    rows = [member_row(item, names) for item in members if isinstance(item, dict)]
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    suffix = {"md": ".md", "csv": ".csv", "jsonl": ".jsonl"}[fmt]
    path = out or (default_reports_dir() / f"{guild_id}-members-{stamp}{suffix}")
    _write_report(rows, path, fmt, guild_id=guild_id)
    summary = {"path": str(path), "count": len(rows), "guild_id": guild_id}
    emit(summary, as_json=as_json, rows=[summary])


def cmd_audit(
    token: str,
    guild_id: str,
    as_json: bool,
    *,
    limit: int,
    user_id: str | None,
    action_type: int | None,
) -> None:
    """``GET /guilds/{guild.id}/audit-logs`` (needs ``VIEW_AUDIT_LOG``)."""
    params: dict[str, Any] = {"limit": max(1, min(limit, AUDIT_LIMIT_MAX))}
    if user_id:
        params["user_id"] = user_id
    if action_type is not None:
        params["action_type"] = action_type
    data = request("GET", f"/guilds/{guild_id}/audit-logs", token, params=params)
    entries = data.get("audit_log_entries", []) if isinstance(data, dict) else []
    users = {
        str(user.get("id")): user.get("username", "")
        for user in (data.get("users") or [] if isinstance(data, dict) else [])
        if isinstance(user, dict)
    }
    rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        actor = str(entry.get("user_id") or "")
        rows.append(
            {
                "id": entry.get("id", ""),
                "action_type": entry.get("action_type", ""),
                "target_id": entry.get("target_id") or "",
                "user_id": actor,
                "username": users.get(actor, ""),
                "reason": entry.get("reason") or "",
            }
        )
    emit(data, as_json=as_json, rows=rows)


def cmd_channel_create(
    token: str,
    guild_id: str,
    as_json: bool,
    *,
    name: str,
    type_id: int,
    parent_id: str | None,
    topic: str | None,
    nsfw: bool | None,
    position: int | None,
    reason: str | None,
    yes: bool,
) -> None:
    """``POST /guilds/{guild.id}/channels`` (needs ``MANAGE_CHANNELS``)."""
    if not 1 <= len(name) <= CHANNEL_NAME_MAX:
        die(f"channel name must be 1–{CHANNEL_NAME_MAX} characters")
    payload: dict[str, Any] = {"name": name, "type": type_id}
    if parent_id:
        payload["parent_id"] = parent_id
    if topic is not None:
        payload["topic"] = topic
    if nsfw is not None:
        payload["nsfw"] = nsfw
    if position is not None:
        payload["position"] = position
    confirm_write(
        f"Create channel {name!r} (type {channel_type_label(type_id)}) in guild {guild_id}?",
        yes=yes,
    )
    data = request("POST", f"/guilds/{guild_id}/channels", token, payload=payload, reason=reason)
    emit(data, as_json=as_json, rows=[channel_row(data)] if isinstance(data, dict) else [])


def cmd_channel_edit(
    token: str,
    channel_id: str,
    as_json: bool,
    *,
    name: str | None,
    topic: str | None,
    parent_id: str | None,
    nsfw: bool | None,
    position: int | None,
    reason: str | None,
    yes: bool,
) -> None:
    """``PATCH /channels/{channel.id}`` (needs ``MANAGE_CHANNELS``)."""
    payload: dict[str, Any] = {}
    if name is not None:
        if not 1 <= len(name) <= CHANNEL_NAME_MAX:
            die(f"channel name must be 1–{CHANNEL_NAME_MAX} characters")
        payload["name"] = name
    if topic is not None:
        payload["topic"] = topic
    if parent_id is not None:
        payload["parent_id"] = parent_id or None
    if nsfw is not None:
        payload["nsfw"] = nsfw
    if position is not None:
        payload["position"] = position
    if not payload:
        die("channel-edit needs at least one of --name --topic --parent --nsfw --position")
    confirm_write(f"Modify channel {channel_id} with {payload}?", yes=yes)
    data = request("PATCH", f"/channels/{channel_id}", token, payload=payload, reason=reason)
    emit(data, as_json=as_json, rows=[channel_row(data)] if isinstance(data, dict) else [])


def cmd_channel_delete(
    token: str,
    channel_id: str,
    as_json: bool,
    *,
    reason: str | None,
    yes: bool,
) -> None:
    """``DELETE /channels/{channel.id}`` — cannot be undone for guild channels."""
    confirm_write(
        f"Delete guild channel {channel_id}? This cannot be undone.",
        yes=yes,
    )
    data = request("DELETE", f"/channels/{channel_id}", token, reason=reason)
    emit(data, as_json=as_json, rows=[channel_row(data)] if isinstance(data, dict) else [])


def cmd_channel_move(
    token: str,
    guild_id: str,
    as_json: bool,
    *,
    channel_id: str,
    position: int,
    parent_id: str | None,
    reason: str | None,
    yes: bool,
) -> None:
    """``PATCH /guilds/{guild.id}/channels`` (needs ``MANAGE_CHANNELS``)."""
    entry: dict[str, Any] = {"id": channel_id, "position": position}
    if parent_id is not None:
        entry["parent_id"] = parent_id or None
    confirm_write(f"Move channel {channel_id} in guild {guild_id} to {entry}?", yes=yes)
    request("PATCH", f"/guilds/{guild_id}/channels", token, payload=[entry], reason=reason)
    emit({"ok": True, **entry}, as_json=as_json, rows=[entry])


def build_parser() -> argparse.ArgumentParser:
    """CLI parser."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--env-file", type=Path, help="bot .env to load (does not override env)")
    parser.add_argument("--guild", help="default guild snowflake")
    parser.add_argument("--json", action="store_true", help="print raw/structured JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("me", help="GET /users/@me — token smoke test")
    sub.add_parser("guilds", help="GET /users/@me/guilds — guilds this bot can see")

    guild_p = sub.add_parser("guild", help="GET /guilds/{id}?with_counts=true")
    guild_p.add_argument("guild_id", nargs="?", help="guild snowflake")

    channels_p = sub.add_parser("channels", help="GET /guilds/{id}/channels")
    channels_p.add_argument("guild_id", nargs="?", help="guild snowflake")

    channel_p = sub.add_parser("channel", help="GET /channels/{id}")
    channel_p.add_argument("channel_id", help="channel snowflake")

    roles_p = sub.add_parser("roles", help="GET /guilds/{id}/roles")
    roles_p.add_argument("guild_id", nargs="?", help="guild snowflake")

    counts_p = sub.add_parser("role-counts", help="GET /guilds/{id}/roles/member-counts")
    counts_p.add_argument("guild_id", nargs="?", help="guild snowflake")

    member_p = sub.add_parser(
        "member", help="GET /guilds/{id}/members/{user} (guild from --guild/env)"
    )
    member_p.add_argument("user_id", help="user snowflake")

    members_p = sub.add_parser(
        "members", help="GET /guilds/{id}/members (paginated; needs GUILD_MEMBERS intent)"
    )
    members_p.add_argument("guild_id", nargs="?", help="guild snowflake")
    members_p.add_argument(
        "--max", type=int, default=MEMBERS_DEFAULT_CAP, help="max members to fetch (default 10000)"
    )

    search_p = sub.add_parser(
        "members-search", help="GET /guilds/{id}/members/search (no privileged intent)"
    )
    search_p.add_argument("query", help="username/nickname prefix")
    search_p.add_argument("--limit", type=int, default=100)

    report_p = sub.add_parser("members-report", help="export members to reports/admin-helper/")
    report_p.add_argument("guild_id", nargs="?", help="guild snowflake")
    report_p.add_argument("--max", type=int, default=MEMBERS_DEFAULT_CAP)
    report_p.add_argument("--format", choices=("md", "csv", "jsonl"), default="md")
    report_p.add_argument("--out", type=Path, help="output path (default reports/admin-helper/)")

    audit_p = sub.add_parser("audit", help="GET /guilds/{id}/audit-logs (VIEW_AUDIT_LOG)")
    audit_p.add_argument("guild_id", nargs="?", help="guild snowflake")
    audit_p.add_argument("--limit", type=int, default=50)
    audit_p.add_argument("--user-id")
    audit_p.add_argument("--action-type", type=int)

    create_p = sub.add_parser("channel-create", help="POST /guilds/{id}/channels (destructive)")
    create_p.add_argument("guild_id", nargs="?", help="guild snowflake")
    create_p.add_argument("--name", required=True)
    create_p.add_argument("--type", default="text", dest="channel_type")
    create_p.add_argument("--parent")
    create_p.add_argument("--topic")
    create_p.add_argument("--nsfw", action=argparse.BooleanOptionalAction, default=None)
    create_p.add_argument("--position", type=int)
    create_p.add_argument("--reason")
    create_p.add_argument("--yes", action="store_true")

    edit_p = sub.add_parser("channel-edit", help="PATCH /channels/{id} (destructive)")
    edit_p.add_argument("channel_id")
    edit_p.add_argument("--name")
    edit_p.add_argument("--topic")
    edit_p.add_argument("--parent")
    edit_p.add_argument("--nsfw", action=argparse.BooleanOptionalAction, default=None)
    edit_p.add_argument("--position", type=int)
    edit_p.add_argument("--reason")
    edit_p.add_argument("--yes", action="store_true")

    delete_p = sub.add_parser("channel-delete", help="DELETE /channels/{id} (irreversible)")
    delete_p.add_argument("channel_id")
    delete_p.add_argument("--reason")
    delete_p.add_argument("--yes", action="store_true")

    move_p = sub.add_parser("channel-move", help="PATCH /guilds/{id}/channels positions")
    move_p.add_argument("guild_id", nargs="?", help="guild snowflake")
    move_p.add_argument("--id", required=True, dest="channel_id")
    move_p.add_argument("--position", type=int, required=True)
    move_p.add_argument("--parent")
    move_p.add_argument("--reason")
    move_p.add_argument("--yes", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(args.env_file)
    token = require_token()
    as_json = bool(args.json)
    command = args.command

    if command == "me":
        cmd_me(token, as_json)
    elif command == "guilds":
        cmd_guilds(token, as_json)
    elif command == "guild":
        cmd_guild(token, resolve_guild(args.guild, args.guild_id), as_json)
    elif command == "channels":
        cmd_channels(token, resolve_guild(args.guild, args.guild_id), as_json)
    elif command == "channel":
        cmd_channel(token, args.channel_id, as_json)
    elif command == "roles":
        cmd_roles(token, resolve_guild(args.guild, args.guild_id), as_json)
    elif command == "role-counts":
        cmd_role_counts(token, resolve_guild(args.guild, args.guild_id), as_json)
    elif command == "member":
        cmd_member(token, resolve_guild(args.guild), args.user_id, as_json)
    elif command == "members":
        cmd_members(token, resolve_guild(args.guild, args.guild_id), as_json, cap=args.max)
    elif command == "members-search":
        cmd_members_search(
            token,
            resolve_guild(args.guild),
            args.query,
            as_json,
            args.limit,
        )
    elif command == "members-report":
        cmd_members_report(
            token,
            resolve_guild(args.guild, args.guild_id),
            as_json,
            cap=args.max,
            fmt=args.format,
            out=args.out,
        )
    elif command == "audit":
        cmd_audit(
            token,
            resolve_guild(args.guild, args.guild_id),
            as_json,
            limit=args.limit,
            user_id=args.user_id,
            action_type=args.action_type,
        )
    elif command == "channel-create":
        cmd_channel_create(
            token,
            resolve_guild(args.guild, args.guild_id),
            as_json,
            name=args.name,
            type_id=parse_channel_type(args.channel_type),
            parent_id=args.parent,
            topic=args.topic,
            nsfw=args.nsfw,
            position=args.position,
            reason=args.reason,
            yes=args.yes,
        )
    elif command == "channel-edit":
        cmd_channel_edit(
            token,
            args.channel_id,
            as_json,
            name=args.name,
            topic=args.topic,
            parent_id=args.parent,
            nsfw=args.nsfw,
            position=args.position,
            reason=args.reason,
            yes=args.yes,
        )
    elif command == "channel-delete":
        cmd_channel_delete(token, args.channel_id, as_json, reason=args.reason, yes=args.yes)
    elif command == "channel-move":
        cmd_channel_move(
            token,
            resolve_guild(args.guild, args.guild_id),
            as_json,
            channel_id=args.channel_id,
            position=args.position,
            parent_id=args.parent,
            reason=args.reason,
            yes=args.yes,
        )
    else:
        die(f"unknown command: {command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
