"""Offline tests for the admin-helper CLI (mocked Discord HTTP)."""

from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any, Self
from urllib.error import HTTPError

import pytest


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _queue_urlopen(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, bodies: list[Any]
) -> list[str]:
    """Patch urlopen to return queued JSON bodies; record requested URLs."""
    urls: list[str] = []
    queue = list(bodies)

    def fake_urlopen(req: Any, timeout: float = 0) -> _FakeResponse:
        urls.append(req.full_url)
        if not queue:
            raise AssertionError(f"unexpected request {req.full_url}")
        item = queue.pop(0)
        if isinstance(item, HTTPError):
            raise item
        raw = item if isinstance(item, bytes) else json.dumps(item).encode()
        return _FakeResponse(raw)

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    return urls


def test_parse_channel_type(admin_helper: ModuleType) -> None:
    assert admin_helper.parse_channel_type("text") == 0
    assert admin_helper.parse_channel_type("voice") == 2
    assert admin_helper.parse_channel_type("4") == 4
    with pytest.raises(SystemExit):
        admin_helper.parse_channel_type("nope")


def test_load_env_file_does_not_override(
    admin_helper: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / ".env"
    path.write_text('DISCORD_BOT_TOKEN="from-file"\nDISCORD_GUILD_ID=111\n', encoding="utf-8")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "from-env")
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    admin_helper.load_env_file(path)
    assert admin_helper.os.environ["DISCORD_BOT_TOKEN"] == "from-env"
    assert admin_helper.os.environ["DISCORD_GUILD_ID"] == "111"


def test_resolve_guild_ignores_prod_as_default(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    monkeypatch.setenv("DISCORD_PROD_GUILD_ID", "999")
    monkeypatch.setenv("DISCORD_DEV_GUILD_ID", "111")
    assert admin_helper.resolve_guild(None, None) == "111"
    monkeypatch.delenv("DISCORD_DEV_GUILD_ID", raising=False)
    with pytest.raises(SystemExit):
        admin_helper.resolve_guild(None, None)
    assert admin_helper.resolve_guild("999", None) == "999"


def test_confirm_write_requires_yes_when_not_a_tty(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin_helper.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        admin_helper.confirm_write("delete?", yes=False)
    admin_helper.confirm_write("delete?", yes=True)


def test_redact_token(admin_helper: ModuleType) -> None:
    assert "***" in admin_helper.redact("Bot secret-token failed", "secret-token")
    assert "secret-token" not in admin_helper.redact("Bot secret-token failed", "secret-token")


def test_me(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    _queue_urlopen(monkeypatch, admin_helper, [{"id": "1", "username": "heimdal", "bot": True}])
    assert admin_helper.main(["--json", "me"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["username"] == "heimdal"


def test_members_paginates(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setattr(admin_helper, "MEMBERS_PAGE_MAX", 2)
    page1 = [
        {"user": {"id": "10", "username": "a"}, "roles": [], "joined_at": "t"},
        {"user": {"id": "11", "username": "b"}, "roles": [], "joined_at": "t"},
    ]
    page2 = [{"user": {"id": "12", "username": "c"}, "roles": [], "joined_at": "t"}]
    roles = [{"id": "r1", "name": "Member"}]
    urls = _queue_urlopen(monkeypatch, admin_helper, [page1, page2, roles])
    assert admin_helper.main(["--json", "members", "99", "--max", "3"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [m["user"]["id"] for m in payload] == ["10", "11", "12"]
    assert "after=0" in urls[0]
    assert "after=11" in urls[1]


def test_channel_delete_refuses_without_yes(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    monkeypatch.setattr(admin_helper.sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit):
        admin_helper.main(["channel-delete", "555"])


def test_channel_create_with_yes(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    created = {
        "id": "42",
        "type": 0,
        "name": "reports",
        "parent_id": None,
        "position": 1,
        "topic": None,
    }
    urls = _queue_urlopen(monkeypatch, admin_helper, [created])
    assert (
        admin_helper.main(
            ["--json", "channel-create", "99", "--name", "reports", "--type", "text", "--yes"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["id"] == "42"
    assert urls[0].endswith("/guilds/99/channels")


def test_members_report_writes_markdown(
    admin_helper: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-token")
    members = [
        {
            "user": {"id": "10", "username": "ada", "global_name": "Ada", "bot": False},
            "nick": None,
            "roles": ["r1"],
            "joined_at": "2020-01-01T00:00:00+00:00",
            "pending": False,
        }
    ]
    roles = [{"id": "r1", "name": "Member"}]
    _queue_urlopen(monkeypatch, admin_helper, [members, roles])
    out = tmp_path / "members.md"
    assert admin_helper.main(["--json", "members-report", "99", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "ada" in text
    assert "Member" in text
    summary = json.loads(capsys.readouterr().out)
    assert summary["count"] == 1


def test_api_error_redacts_token(
    admin_helper: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "super-secret")
    err = HTTPError(
        "https://discord.com/api/v10/users/@me",
        401,
        "Unauthorized",
        hdrs=Message(),
        fp=io.BytesIO(b'{"message":"401: Unauthorized","code":0}'),
    )
    _queue_urlopen(monkeypatch, admin_helper, [err])
    with pytest.raises(SystemExit):
        admin_helper.main(["me"])
    err_text = capsys.readouterr().err
    assert "super-secret" not in err_text
    assert "401" in err_text
