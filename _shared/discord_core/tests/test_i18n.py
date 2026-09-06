import json
from pathlib import Path

from discord_core.i18n import Localizer


def test_fallback_chain(tmp_path: Path):
    (tmp_path / "en-US.json").write_text(json.dumps({"hello": "Hello {name}", "only_en": "EN"}))
    (tmp_path / "es-ES.json").write_text(json.dumps({"hello": "Hola {name}"}))
    i18n = Localizer.from_dir(tmp_path)
    assert i18n.t("hello", locale="es-ES", name="Ana") == "Hola Ana"
    assert i18n.t("hello", locale="fr", name="Ana") == "Hello Ana"
    assert i18n.t("only_en", locale="es-ES") == "EN"
    assert i18n.t("missing") == "missing"
    assert i18n.localizations("hello") == {"es-ES": "Hola {name}"}
    assert i18n.localizations("only_en") is None


def test_core_strings_present_without_dir():
    i18n = Localizer.from_dir(None)
    assert "handle" in i18n.t("core.unknown_interaction")
    assert "gestionar" in i18n.t("core.unknown_interaction", locale="es-ES")
