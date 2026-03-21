"""Step 2: ingestion paths, CSV validation, JSONL parsing, and cleaning."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ingestion import (
    employees_csv_path,
    get_data_directory,
    load_employees_dataframe,
    load_telemetry_dataframe,
    telemetry_jsonl_path,
)
from ingestion.cleaning import (
    parse_cost_usd,
    parse_duration_ms,
    parse_iso_timestamp_utc,
    parse_optional_int,
    parse_tool_success,
)
from ingestion.telemetry import iter_telemetry_rows

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_get_data_directory_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVECTUS_DATA_DIR", raising=False)
    d = get_data_directory()
    assert d.name == "output"


def test_get_data_directory_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(tmp_path))
    assert get_data_directory() == tmp_path.resolve()


def test_employees_csv_path_uses_base(tmp_path: Path) -> None:
    p = employees_csv_path(tmp_path)
    assert p == tmp_path / "employees.csv"


def test_load_employees_dataframe_ok() -> None:
    df = load_employees_dataframe(FIXTURES / "employees_min.csv")
    assert len(df) == 2
    assert set(df.columns) >= {"email", "full_name", "practice", "level", "location"}


def test_load_employees_missing_column(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("email,x\na@example.com,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_employees_dataframe(bad)


def test_load_employees_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_employees_dataframe(tmp_path / "nope.csv")


def test_load_telemetry_from_fixtures() -> None:
    df = load_telemetry_dataframe(FIXTURES / "telemetry_min.jsonl")
    assert len(df) == 4
    row0 = df.iloc[0]
    assert row0["user_email"] == "a@example.com"
    assert row0["cost_usd"] == pytest.approx(0.012)
    assert row0["duration_ms"] == 100
    assert row0["input_tokens"] == 10
    assert row0["resource_practice"] == "Data Engineering"

    bad_numeric = df[df["log_event_id"] == "ev2"].iloc[0]
    assert pd.isna(bad_numeric["cost_usd"])
    assert pd.isna(bad_numeric["duration_ms"])

    tool = df[df["event_name"] == "tool_result"].iloc[0]
    assert tool["tool_success"] is True
    assert tool["tool_decision"] == "reject"
    assert tool["tool_name"] == "Edit"

    err = df[df["event_name"] == "api_error"].iloc[0]
    assert err["error_detail"] == "credentials missing"
    assert err["status_code"] == "401"


def test_telemetry_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_telemetry_dataframe(tmp_path / "missing.jsonl")


def test_telemetry_invalid_json_line(tmp_path: Path) -> None:
    p = tmp_path / "bad.jsonl"
    p.write_text("{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        list(iter_telemetry_rows(p))


def test_telemetry_empty_log_events(tmp_path: Path) -> None:
    p = tmp_path / "empty.jsonl"
    p.write_text('{"messageType": "X", "logEvents": []}\n', encoding="utf-8")
    df = load_telemetry_dataframe(p)
    assert df.empty


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.5", 1.5),
        ("", None),
        ("x", None),
        (None, None),
    ],
)
def test_parse_cost_usd(raw: str | None, expected: float | None) -> None:
    assert parse_cost_usd(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("100", 100),
        ("99.7", 100),
        ("", None),
        ("nope", None),
    ],
)
def test_parse_duration_ms(raw: str | None, expected: int | None) -> None:
    assert parse_duration_ms(raw) == expected


def test_parse_iso_timestamp_z() -> None:
    dt = parse_iso_timestamp_utc("2025-12-01T10:00:00.000Z")
    assert dt is not None
    assert dt.year == 2025
    assert dt.month == 12


def test_parse_optional_int_empty_string() -> None:
    assert parse_optional_int("") is None


def test_parse_tool_success() -> None:
    assert parse_tool_success("true") is True
    assert parse_tool_success("FALSE") is False
    assert parse_tool_success("") is None
