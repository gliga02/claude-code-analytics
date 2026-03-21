"""Step 1: SQLite schema, indexes, and database path configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select

from database import (
    Employee,
    Event,
    create_engine_instance,
    create_session_factory,
    get_database_path,
    init_schema,
)


def test_get_database_path_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PROVECTUS_DATABASE_PATH", raising=False)
    # Project root is fixed; default path should end with data/analytics.db
    p = get_database_path()
    assert p.name == "analytics.db"
    assert p.parent.name == "data"


def test_get_database_path_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom = tmp_path / "custom" / "db.sqlite"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(custom))
    assert get_database_path() == custom.resolve()


def test_init_schema_creates_tables_and_indexes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db_file))
    engine = create_engine_instance(echo=False)
    init_schema(engine)
    assert db_file.is_file()

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "employees" in tables
    assert "events" in tables

    emp_indexes = {idx["name"]: idx for idx in insp.get_indexes("employees")}
    assert "ix_employees_email" in emp_indexes
    assert "ix_employees_practice" in emp_indexes
    assert "ix_employees_level" in emp_indexes

    ev_indexes = {idx["name"]: idx for idx in insp.get_indexes("events")}
    assert "ix_events_user_email" in ev_indexes
    assert "ix_events_employee_id" in ev_indexes
    assert "ix_events_event_ts" in ev_indexes
    assert "ix_events_event_name" in ev_indexes
    assert "ix_events_session_id" in ev_indexes
    assert "ix_events_resource_practice" in ev_indexes
    assert "ix_events_user_email_event_ts" in ev_indexes
    assert "ix_events_practice_event_ts" in ev_indexes

    emp_cols = {c["name"] for c in insp.get_columns("employees")}
    assert "email" in emp_cols
    uq_events = insp.get_unique_constraints("events")
    assert any("log_event_id" in (u.get("column_names") or ()) for u in uq_events)


def test_session_factory_inserts_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "roundtrip.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db_file))
    engine = create_engine_instance()
    init_schema(engine)
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        emp = Employee(
            email="a@example.com",
            full_name="A",
            practice="Data Engineering",
            level="L5",
            location="Germany",
        )
        session.add(emp)
        session.commit()
        session.refresh(emp)
        ev = Event(
            user_email="a@example.com",
            employee_id=emp.id,
            event_name="api_request",
            cost_usd=0.01,
            duration_ms=100,
        )
        session.add(ev)
        session.commit()

    with SessionLocal() as session:
        loaded = session.scalars(select(Event).where(Event.user_email == "a@example.com")).one()
        assert loaded.employee_id == 1
        assert loaded.cost_usd == pytest.approx(0.01)
