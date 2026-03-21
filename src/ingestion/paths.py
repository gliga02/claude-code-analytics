"""Resolve canonical data directory (CSV and JSONL)."""

from __future__ import annotations

import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_data_directory() -> Path:
    """Directory containing employees.csv and telemetry_logs.jsonl.

    Override with environment variable PROVECTUS_DATA_DIR. When unset, uses
    project_root/output/.
    """
    raw = os.environ.get("PROVECTUS_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    return (_project_root() / "output").resolve()


def employees_csv_path(base: Path | None = None) -> Path:
    root = base if base is not None else get_data_directory()
    return root / "employees.csv"


def telemetry_jsonl_path(base: Path | None = None) -> Path:
    root = base if base is not None else get_data_directory()
    return root / "telemetry_logs.jsonl"
