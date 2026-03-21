"""Step 3: ETL load into SQLite with email join to employees."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from database import Employee, Event, create_engine_instance, create_session_factory, load_database

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_load_database_fixture_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = tmp_path / "etl.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(FIXTURES))

    n_emp, n_ev = load_database()
    assert n_emp == 2
    assert n_ev == 4

    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        na = session.scalar(
            select(func.count()).select_from(Event).where(Event.user_email == "a@example.com")
        )
        nb = session.scalar(
            select(func.count()).select_from(Event).where(Event.user_email == "b@example.com")
        )
        assert na == 3
        assert nb == 1


def test_load_database_joins_employee_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = tmp_path / "etl.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(FIXTURES))

    load_database()
    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        emp_a = session.scalars(select(Event).where(Event.user_email == "a@example.com")).all()
        assert all(e.employee_id is not None for e in emp_a)
        first = emp_a[0]
        assert first.employee is not None
        assert first.employee.email == "a@example.com"


def test_load_database_truncates_and_reload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = tmp_path / "etl.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(FIXTURES))

    load_database()
    load_database()
    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Employee)) == 2
        assert session.scalar(select(func.count()).select_from(Event)) == 4


def test_event_unknown_email_has_null_employee_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "employees.csv").write_text(
        "email,full_name,practice,level,location\n"
        "only@example.com,Only,DE,L1,X\n",
        encoding="utf-8",
    )
    inner = {
        "body": "claude_code.api_request",
        "attributes": {
            "event.timestamp": "2025-12-01T10:00:00.000Z",
            "user.email": "missing@example.com",
            "session.id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "event.name": "api_request",
            "cost_usd": "0.01",
            "duration_ms": "10",
        },
        "resource": {"user.practice": "Data Engineering"},
    }
    batch = {
        "logEvents": [
            {
                "id": "u1",
                "timestamp": 1,
                "message": json.dumps(inner),
            }
        ]
    }
    (data / "telemetry_logs.jsonl").write_text(json.dumps(batch) + "\n", encoding="utf-8")

    db = tmp_path / "u.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(data))

    load_database()
    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        ev = session.scalars(select(Event)).one()
        assert ev.user_email == "missing@example.com"
        assert ev.employee_id is None


def test_load_database_respects_event_batch_size(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = tmp_path / "etl.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(FIXTURES))

    n_emp, n_ev = load_database(event_batch_size=2)
    assert n_emp == 2
    assert n_ev == 4
