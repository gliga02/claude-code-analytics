"""Load and validate employees.csv."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_EMPLOYEE_COLUMNS = ("email", "full_name", "practice", "level", "location")


def load_employees_dataframe(csv_path: Path) -> pd.DataFrame:
    """Read employees CSV and validate required columns."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Employees CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    missing = set(REQUIRED_EMPLOYEE_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Employees CSV missing columns: {sorted(missing)}")
    return df
