"""Step 5: Streamlit app helpers and view entrypoints (no full Streamlit runtime)."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app import (
    compute_platform_metrics,
    filter_developer_events,
    render_developer_view,
    render_management_view,
)


def test_compute_platform_metrics_empty() -> None:
    df = pd.DataFrame()
    m = compute_platform_metrics(df)
    assert m["event_count"] == 0
    assert m["total_cost_usd"] == 0.0
    assert m["distinct_users"] == 0


def test_compute_platform_metrics_basic() -> None:
    df = pd.DataFrame(
        {
            "user_email": ["a@x.com", "b@x.com"],
            "cost_usd": [1.0, None],
        }
    )
    m = compute_platform_metrics(df)
    assert m["event_count"] == 2
    assert m["total_cost_usd"] == pytest.approx(1.0)
    assert m["distinct_users"] == 2


def test_filter_developer_events_by_name_and_email() -> None:
    df = pd.DataFrame(
        {
            "event_ts": pd.to_datetime(
                ["2025-01-02T00:00:00Z", "2025-01-01T00:00:00Z"],
                utc=True,
            ),
            "event_name": ["api_request", "tool_result"],
            "user_email": ["a@example.com", "b@example.com"],
        }
    )
    out = filter_developer_events(df, ["api_request"], "a@")
    assert len(out) == 1
    assert out.iloc[0]["event_name"] == "api_request"


def test_view_functions_are_callable_signatures() -> None:
    assert len(inspect.signature(render_management_view).parameters) == 1
    assert len(inspect.signature(render_developer_view).parameters) == 1


def test_render_views_with_mocked_streamlit() -> None:
    with patch("app.st", MagicMock()):
        render_management_view(pd.DataFrame())
        render_developer_view(pd.DataFrame())


def test_run_dashboard_callable() -> None:
    from app import run_dashboard

    assert callable(run_dashboard)
