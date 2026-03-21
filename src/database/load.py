"""ETL: load employees.csv and telemetry JSONL into SQLite."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from database.models import Employee, Event
from database.session import create_engine_instance, create_session_factory, init_schema
from ingestion import (
    employees_csv_path,
    iter_telemetry_rows,
    load_employees_dataframe,
    telemetry_jsonl_path,
)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _truncate_optional(value: Any, max_len: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) <= max_len:
        return s
    return s[:max_len]


def _clean_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _clean_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _build_event(row: dict[str, Any], email_to_id: dict[str, int]) -> Event:
    email = row.get("user_email")
    if not email or not str(email).strip():
        raise ValueError("event row missing user_email")
    email_s = str(email).strip()
    return Event(
        employee_id=email_to_id.get(email_s),
        user_email=_truncate_optional(email_s, 512) or email_s[:512],
        log_event_id=_truncate_optional(row.get("log_event_id"), 128),
        event_ts=row.get("event_ts"),
        session_id=_truncate_optional(row.get("session_id"), 64),
        body=_truncate_optional(row.get("body"), 256),
        event_name=_truncate_optional(row.get("event_name"), 128),
        cost_usd=_clean_float(row.get("cost_usd")),
        duration_ms=_clean_int(row.get("duration_ms")),
        input_tokens=_clean_int(row.get("input_tokens")),
        output_tokens=_clean_int(row.get("output_tokens")),
        cache_creation_tokens=_clean_int(row.get("cache_creation_tokens")),
        cache_read_tokens=_clean_int(row.get("cache_read_tokens")),
        model=_truncate_optional(row.get("model"), 256),
        tool_name=_truncate_optional(row.get("tool_name"), 128),
        tool_success=row.get("tool_success"),
        tool_decision=_truncate_optional(row.get("tool_decision"), 64),
        error_detail=_optional_text(row.get("error_detail")),
        status_code=_truncate_optional(row.get("status_code"), 64),
        resource_practice=_truncate_optional(row.get("resource_practice"), 256),
    )


def _clear_tables(session: Session) -> None:
    """Remove all events then employees (FK-safe order)."""
    session.execute(delete(Event))
    session.execute(delete(Employee))
    session.commit()


def load_database(
    *,
    engine: Engine | None = None,
    data_dir: Path | None = None,
    event_batch_size: int = 5000,
    echo: bool = False,
) -> tuple[int, int]:
    """Replace all employees and events from CSV and JSONL under data_dir.

    Uses a truncate-and-reload strategy: deletes existing rows, then inserts
    employees, then streams telemetry rows in batches. Resolves
    ``employee_id`` on each event when ``user_email`` matches an employee row.

    Returns ``(employee_count, event_count)``.
    """
    engine = engine or create_engine_instance(echo=echo)
    init_schema(engine)

    root = data_dir
    emp_path = employees_csv_path(root)
    tel_path = telemetry_jsonl_path(root)

    emp_df = load_employees_dataframe(emp_path)
    SessionLocal = create_session_factory(engine)

    with SessionLocal() as session:
        _clear_tables(session)

        for rec in emp_df.to_dict("records"):
            session.add(
                Employee(
                    email=str(rec["email"]).strip(),
                    full_name=_truncate_optional(rec.get("full_name"), 512),
                    practice=_truncate_optional(rec.get("practice"), 256),
                    level=_truncate_optional(rec.get("level"), 32),
                    location=_truncate_optional(rec.get("location"), 128),
                )
            )
        session.commit()

        employees = list(session.scalars(select(Employee)).all())
        email_to_id = {e.email: e.id for e in employees}
        employee_count = len(employees)

        event_count = 0
        batch: list[Event] = []
        for row in iter_telemetry_rows(tel_path):
            batch.append(_build_event(row, email_to_id))
            event_count += 1
            if len(batch) >= event_batch_size:
                session.add_all(batch)
                session.commit()
                batch.clear()
        if batch:
            session.add_all(batch)
            session.commit()

    return employee_count, event_count
