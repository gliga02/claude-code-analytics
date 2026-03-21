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


def fetch_events_developer_dataframe(session: Session) -> pd.DataFrame:
    """Wider event projection for technical drilldowns in the Developer view."""
    stmt = (
        select(
            Event.id.label("event_id"),
            Event.log_event_id,
            Event.event_ts,
            Event.session_id,
            Event.user_email,
            Event.body,
            Event.event_name,
            Event.cost_usd,
            Event.duration_ms,
            Event.input_tokens,
            Event.output_tokens,
            Event.tool_name,
            Event.tool_success,
            Event.tool_decision,
            Event.error_detail,
            Event.status_code,
            Event.model,
            Event.employee_id,
            func.coalesce(Employee.practice, Event.resource_practice, literal("Unknown")).label("practice"),
            func.coalesce(Employee.level, literal("Unknown")).label("level"),
        )
        .select_from(Event)
        .outerjoin(Employee, Event.employee_id == Employee.id)
    )
    return pd.read_sql(stmt, session.connection())
