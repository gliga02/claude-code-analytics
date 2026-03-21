"""Step 0: repository layout and dependency smoke tests."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"


def test_project_root_contains_expected_paths() -> None:
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "requirements.txt").is_file()
    assert (PROJECT_ROOT / "requirements-dev.txt").is_file()
    assert (PROJECT_ROOT / "README.md").is_file()
    assert (PROJECT_ROOT / "docs" / "PLAN.md").is_file()
    assert (PROJECT_ROOT / "docs" / "AGENTS.md").is_file()
    assert (PROJECT_ROOT / "docs" / "README.md").is_file()
    assert (PROJECT_ROOT / "AGENTS.md").is_file()
    assert (SRC / "ingestion" / "__init__.py").is_file()
    assert (SRC / "database" / "__init__.py").is_file()
    assert (SRC / "analytics" / "__init__.py").is_file()
    assert (SRC / "app.py").is_file()


@pytest.mark.parametrize(
    "module_name",
    [
        "pandas",
        "streamlit",
        "sqlalchemy",
        "plotly",
        "sklearn",
    ],
)
def test_runtime_dependencies_import(module_name: str) -> None:
    importlib.import_module(module_name)


def test_package_modules_importable() -> None:
    """Ensure pytest pythonpath includes src (see pyproject.toml)."""
    import ingestion
    import database
    import analytics

    assert ingestion.__doc__
    assert database.__doc__
    assert analytics.__doc__


def test_requirements_txt_matches_pyproject_runtime_deps() -> None:
    """Keep requirements.txt aligned with pyproject.toml [project.dependencies]."""
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    req = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")
    in_deps = False
    expected: list[str] = []
    for raw in pyproject.splitlines():
        line = raw.strip()
        if line.startswith("dependencies = ["):
            in_deps = True
            continue
        if in_deps:
            if line.startswith("]"):
                break
            if not line or line.startswith("#"):
                continue
            spec = line.rstrip(",").strip()
            if spec.startswith('"') and spec.endswith('"'):
                spec = spec[1:-1]
            if spec:
                expected.append(spec)
    assert expected, "expected [project.dependencies] entries in pyproject.toml"
    for spec in expected:
        assert spec in req, f"missing {spec!r} in requirements.txt"


def test_app_module_importable() -> None:
    import app as app_module

    assert hasattr(app_module, "main")
    assert hasattr(app_module, "run_dashboard")
    assert hasattr(app_module, "render_management_view")
    assert hasattr(app_module, "render_developer_view")
    app_module.main()
