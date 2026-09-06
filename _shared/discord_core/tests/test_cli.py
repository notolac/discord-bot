import uvicorn

from discord_core.cli import run_cli
from discord_core.router import Router
from discord_core.settings import DiscordSettings


def test_serve_reload_passes_import_string(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_APP_ID", "1")
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", "00")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "t")
    captured: dict = {}

    def fake_run(target, **kwargs):
        captured["target"] = target
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    (tmp_path / "src").mkdir()
    code = run_cli(
        bot_name="heimdal",
        router=Router(),
        commands=[],
        settings_cls=DiscordSettings,
        bot_root=tmp_path,
        argv=["serve", "--reload", "--host", "127.0.0.1", "--port", "8000"],
    )
    assert code == 0
    assert captured["target"] == "heimdal.asgi:app"
    assert captured["factory"] is True
    assert captured["reload"] is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000


def test_serve_without_reload_passes_app_object(monkeypatch):
    monkeypatch.setenv("DISCORD_APP_ID", "1")
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", "00")
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "t")
    captured: dict = {}

    def fake_run(target, **kwargs):
        captured["target"] = target
        captured.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    code = run_cli(
        bot_name="heimdal",
        router=Router(),
        commands=[],
        settings_cls=DiscordSettings,
        bot_root=None,
        argv=["serve"],
    )
    assert code == 0
    assert captured["target"] is not None
    assert not isinstance(captured["target"], str)
    assert "reload" not in captured or not captured.get("reload")
