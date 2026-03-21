"""Load joined events into a single analytics DataFrame."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from database.models import Employee, Event


def fetch_events_analysis_dataframe(session: Session) -> pd.DataFrame:
    """Return events with practice and level labels (coalesce directory and resource)."""
    stmt = (
        select(
            Event.id.label("event_id"),
            Event.event_ts,
            Event.cost_usd,
            Event.input_tokens,
            Event.output_tokens,
            Event.cache_creation_tokens,
            Event.cache_read_tokens,
            Event.event_name,
            Event.tool_name,
            Event.tool_success,
            Event.error_detail,
            Event.status_code,
            Event.model,
            Event.user_email,
            func.coalesce(Employee.practice, Event.resource_practice, literal("Unknown")).label("practice"),
            func.coalesce(Employee.level, literal("Unknown")).label("level"),
        )
        .select_from(Event)
        .outerjoin(Employee, Event.employee_id == Employee.id)
    )
    return pd.read_sql(stmt, session.connection())
