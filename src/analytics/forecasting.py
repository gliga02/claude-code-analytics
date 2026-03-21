"""Linear regression forecasts for daily cost series."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from analytics.constants import (
    FORECAST_HORIZON_DAYS,
    FORECAST_INSUFFICIENT_MESSAGE,
    MIN_HISTORY_DAYS,
)


@dataclass(frozen=True)
class CostForecastResult:
    """Result of a daily cost forecast (total or single practice)."""

    sufficient_data: bool
    insufficient_message: str | None
    historical: pd.DataFrame
    forecast_day_start: pd.Series | None
    forecast_cost_usd: np.ndarray | None


def _daily_cost_by_day(df: pd.DataFrame, practice: str | None) -> pd.DataFrame:
    d = df.copy()
    if practice is not None:
        d = d[d["practice"] == practice]
    d = d.dropna(subset=["event_ts"])
    if d.empty:
        return pd.DataFrame(columns=["day", "cost_usd"])
    d["event_dt"] = pd.to_datetime(d["event_ts"], utc=True)
    d["day"] = d["event_dt"].dt.normalize()
    daily = d.groupby("day", as_index=False)["cost_usd"].sum(min_count=0)
    daily["cost_usd"] = daily["cost_usd"].fillna(0.0)
    return daily.sort_values("day").reset_index(drop=True)


def _fit_linear_cost_forecast(daily: pd.DataFrame) -> CostForecastResult:
    if daily.empty or int(daily["day"].nunique()) < MIN_HISTORY_DAYS:
        return CostForecastResult(
            sufficient_data=False,
            insufficient_message=FORECAST_INSUFFICIENT_MESSAGE,
            historical=daily,
            forecast_day_start=None,
            forecast_cost_usd=None,
        )

    n = len(daily)
    x = np.arange(n, dtype=float).reshape(-1, 1)
    y = daily["cost_usd"].astype(float).to_numpy()
    model = LinearRegression()
    model.fit(x, y)
    x_future = np.arange(n, n + FORECAST_HORIZON_DAYS, dtype=float).reshape(-1, 1)
    y_future = model.predict(x_future)

    last_day = pd.Timestamp(daily["day"].iloc[-1])
    offset = pd.to_timedelta(np.arange(1, FORECAST_HORIZON_DAYS + 1), unit="D")
    forecast_days = pd.Series(last_day + offset, name="forecast_day")

    return CostForecastResult(
        sufficient_data=True,
        insufficient_message=None,
        historical=daily,
        forecast_day_start=forecast_days,
        forecast_cost_usd=y_future,
    )


def forecast_daily_total_cost(df: pd.DataFrame) -> CostForecastResult:
    """Forecast total daily cost across all practices (30 days, min 14 history days)."""
    daily = _daily_cost_by_day(df, practice=None)
    return _fit_linear_cost_forecast(daily)


def forecast_cost_by_practice(df: pd.DataFrame) -> dict[str, CostForecastResult]:
    """One forecast per distinct practice label in the frame."""
    if df.empty or "practice" not in df.columns:
        return {}
    practices = sorted({str(p) for p in df["practice"].dropna().unique()})
    out: dict[str, CostForecastResult] = {}
    for p in practices:
        daily = _daily_cost_by_day(df, practice=p)
        out[p] = _fit_linear_cost_forecast(daily)
    return out


def forecast_result_to_dict(result: CostForecastResult) -> dict[str, Any]:
    """Serialize a forecast for JSON-friendly consumers (optional)."""
    payload: dict[str, Any] = {
        "sufficient_data": result.sufficient_data,
        "insufficient_message": result.insufficient_message,
    }
    if result.forecast_day_start is not None:
        payload["forecast_day_start"] = result.forecast_day_start.dt.strftime("%Y-%m-%d").tolist()
    if result.forecast_cost_usd is not None:
        payload["forecast_cost_usd"] = result.forecast_cost_usd.astype(float).tolist()
    return payload
