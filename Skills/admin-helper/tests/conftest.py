"""Fixtures for the admin-helper CLI tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "admin_helper.py"


@pytest.fixture
def admin_helper() -> ModuleType:
    """Load ``admin_helper.py`` as a module (not a package)."""
    spec = importlib.util.spec_from_file_location("admin_helper", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["admin_helper"] = module
    spec.loader.exec_module(module)
    return module
