"""Aggregates, operational metrics, and forecasting."""

from analytics.constants import (
    FORECAST_HORIZON_DAYS,
    FORECAST_INSUFFICIENT_MESSAGE,
    MIN_HISTORY_DAYS,
)
from analytics.forecasting import (
    CostForecastResult,
    forecast_cost_by_practice,
    forecast_daily_total_cost,
    forecast_result_to_dict,
)
from analytics.health import api_error_summary, tool_success_summary
from analytics.io import fetch_events_analysis_dataframe, fetch_events_developer_dataframe
from analytics.temporal import peak_usage_by_hour, peak_usage_by_weekday
from analytics.trends import usage_by_practice_level

__all__ = [
    "FORECAST_HORIZON_DAYS",
    "FORECAST_INSUFFICIENT_MESSAGE",
    "MIN_HISTORY_DAYS",
    "CostForecastResult",
    "api_error_summary",
    "fetch_events_analysis_dataframe",
    "fetch_events_developer_dataframe",
    "forecast_cost_by_practice",
    "forecast_daily_total_cost",
    "forecast_result_to_dict",
    "peak_usage_by_hour",
    "peak_usage_by_weekday",
    "tool_success_summary",
    "usage_by_practice_level",
]
