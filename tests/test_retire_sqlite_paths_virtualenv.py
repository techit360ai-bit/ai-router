"""The SQLite-retirement release gate must scan runtime code only.

A local virtualenv inside the repository (.venv/venv) contains third-party
packages that legitimately import sqlite3; scanning it failed the gate on any
machine that keeps its virtualenv in the repo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gate():
    path = Path(__file__).resolve().parents[1] / "scripts" / "retire_sqlite_paths.py"
    spec = importlib.util.spec_from_file_location("retire_sqlite_paths_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_virtualenvs_are_not_scanned_but_runtime_code_is(tmp_path, monkeypatch) -> None:
    gate = _load_gate()
    for venv in (".venv", "venv"):
        package = tmp_path / venv / "lib" / "python3.11" / "site-packages"
        package.mkdir(parents=True)
        (package / "third_party.py").write_text("import sqlite3\n")
    (tmp_path / "service.py").write_text("print('postgres only')\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    assert gate.violations() == []

    (tmp_path / "service.py").write_text("import sqlite3\n")
    assert [item["path"] for item in gate.violations()] == ["service.py"]
