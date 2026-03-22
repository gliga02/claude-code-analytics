"""Step 4: analytics aggregates, health metrics, temporal peaks, forecasts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from analytics import (
    FORECAST_HORIZON_DAYS,
    FORECAST_INSUFFICIENT_MESSAGE,
    MIN_HISTORY_DAYS,
    api_error_summary,
    fetch_events_analysis_dataframe,
    forecast_cost_by_practice,
    forecast_daily_total_cost,
    peak_usage_by_hour,
    peak_usage_by_weekday,
    tool_success_summary,
    usage_by_practice_level,
)
from database import create_engine_instance, create_session_factory, load_database

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_usage_by_practice_level_sums() -> None:
    df = pd.DataFrame(
        {
            "practice": ["A", "A", "B"],
            "level": ["L1", "L1", "L2"],
            "cost_usd": [1.0, 2.0, None],
            "input_tokens": [10, 5, 1],
            "output_tokens": [0, 5, 2],
            "cache_creation_tokens": [0, 0, 0],
            "cache_read_tokens": [0, 0, 0],
        }
    )
    out = usage_by_practice_level(df)
    row_a = out[(out["practice"] == "A") & (out["level"] == "L1")].iloc[0]
    assert row_a["total_cost_usd"] == pytest.approx(3.0)
    assert row_a["total_tokens"] == 20
    assert row_a["event_count"] == 2


def test_tool_success_summary() -> None:
    df = pd.DataFrame(
        {
            "event_name": ["tool_result", "tool_result", "tool_result", "api_request"],
            "tool_success": [True, True, False, None],
        }
    )
    out = tool_success_summary(df)
    assert len(out) == 2
    assert out["event_count"].sum() == 3
    assert pytest.approx(out["share_of_tool_results"].sum()) == 1.0


def test_api_error_summary() -> None:
    df = pd.DataFrame(
        {
            "event_name": ["api_error", "api_error", "api_error"],
            "error_detail": ["e1", "e1", "e2"],
            "model": ["m1", "m1", "m1"],
            "status_code": ["401", "401", "500"],
        }
    )
    out = api_error_summary(df)
    assert out.iloc[0]["event_count"] == 2
    assert out.iloc[0]["error_detail"] == "e1"


def test_peak_usage_by_hour_orders_by_volume() -> None:
    base = _utc(2025, 6, 2, 9, 0, 0)
    df = pd.DataFrame(
        {
            "event_ts": [
                base,
                base + timedelta(hours=1),
                base + timedelta(hours=1),
                base + timedelta(hours=2),
            ],
            "cost_usd": [1.0, 1.0, 1.0, 5.0],
        }
    )
    out = peak_usage_by_hour(df)
    assert out.iloc[0]["hour_utc"] == 10
    assert out.iloc[0]["event_count"] == 2


def test_peak_usage_by_weekday_monday_first() -> None:
    # Monday 2025-06-02
    mon = _utc(2025, 6, 2, 12, 0, 0)
    tue = _utc(2025, 6, 3, 12, 0, 0)
    df = pd.DataFrame({"event_ts": [mon, mon, tue], "cost_usd": [1.0, 1.0, 3.0]})
    out = peak_usage_by_weekday(df)
    assert out.iloc[0]["weekday"] == "Monday"
    assert out.iloc[1]["weekday"] == "Tuesday"


def test_forecast_daily_total_insufficient_days() -> None:
    base = _utc(2025, 1, 1, 0, 0, 0)
    rows = []
    for i in range(MIN_HISTORY_DAYS - 1):
        rows.append(
            {
                "event_ts": base + timedelta(days=i),
                "cost_usd": 1.0,
                "practice": "P",
                "level": "L1",
            }
        )
    df = pd.DataFrame(rows)
    res = forecast_daily_total_cost(df)
    assert res.sufficient_data is False
    assert res.insufficient_message == FORECAST_INSUFFICIENT_MESSAGE
    assert res.forecast_cost_usd is None


def test_forecast_daily_total_returns_thirty_points() -> None:
    base = _utc(2025, 1, 1, 0, 0, 0)
    rows = []
    for i in range(MIN_HISTORY_DAYS):
        rows.append(
            {
                "event_ts": base + timedelta(days=i),
                "cost_usd": float(i + 1),
                "practice": "P",
                "level": "L1",
            }
        )
    df = pd.DataFrame(rows)
    res = forecast_daily_total_cost(df)
    assert res.sufficient_data is True
    assert res.insufficient_message is None
    assert res.forecast_cost_usd is not None
    assert len(res.forecast_cost_usd) == FORECAST_HORIZON_DAYS
    assert res.forecast_day_start is not None
    assert len(res.forecast_day_start) == FORECAST_HORIZON_DAYS


def test_forecast_by_practice_mixed_sufficiency() -> None:
    base = _utc(2025, 2, 1, 0, 0, 0)
    rows = []
    for i in range(MIN_HISTORY_DAYS):
        rows.append(
            {
                "event_ts": base + timedelta(days=i),
                "cost_usd": 2.0,
                "practice": "Alpha",
                "level": "L1",
            }
        )
    for i in range(3):
        rows.append(
            {
                "event_ts": base + timedelta(days=i),
                "cost_usd": 1.0,
                "practice": "Beta",
                "level": "L2",
            }
        )
    df = pd.DataFrame(rows)
    by_p = forecast_cost_by_practice(df)
    assert by_p["Alpha"].sufficient_data is True
    assert by_p["Alpha"].forecast_cost_usd is not None
    assert len(by_p["Alpha"].forecast_cost_usd) == FORECAST_HORIZON_DAYS
    assert by_p["Beta"].sufficient_data is False
    assert by_p["Beta"].insufficient_message == FORECAST_INSUFFICIENT_MESSAGE


def test_integration_sqlite_fixture_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db = tmp_path / "a4.db"
    monkeypatch.setenv("PROVECTUS_DATABASE_PATH", str(db))
    monkeypatch.setenv("PROVECTUS_DATA_DIR", str(FIXTURES))
    load_database()
    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        df = fetch_events_analysis_dataframe(session)
    assert not df.empty
    trends = usage_by_practice_level(df)
    assert not trends.empty
    assert "total_cost_usd" in trends.columns


def test_forecast_linear_trend_numpy_close() -> None:
    """Deterministic y = 2x + 3; next point should match slope 2."""
    base = _utc(2025, 3, 1, 0, 0, 0)
    rows = []
    for i in range(MIN_HISTORY_DAYS):
        rows.append(
            {
                "event_ts": base + timedelta(days=i),
                "cost_usd": 2.0 * i + 3.0,
                "practice": "P",
                "level": "L1",
            }
        )
    df = pd.DataFrame(rows)
    res = forecast_daily_total_cost(df)
    assert res.sufficient_data
    assert res.forecast_cost_usd is not None
    expected_next = 2.0 * MIN_HISTORY_DAYS + 3.0
    assert res.forecast_cost_usd[0] == pytest.approx(expected_next, rel=1e-5, abs=1e-5)
    assert res.chart_uses_train_test_split is False
    assert res.r2_in_sample is not None
    assert res.r2_in_sample == pytest.approx(1.0, abs=1e-9)
    assert res.mae_in_sample is not None
    assert res.mae_in_sample == pytest.approx(0.0, abs=1e-9)
    assert res.holdout_n_train is not None and res.holdout_n_test is not None
    assert res.holdout_mae is not None
