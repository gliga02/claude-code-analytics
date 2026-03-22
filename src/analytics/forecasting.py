"""Linear regression forecasts for daily cost series."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

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
    # Fit quality: chart model uses all days (no train/test split for the line you see).
    r2_in_sample: float | None = None
    mae_in_sample: float | None = None
    chart_uses_train_test_split: bool = False
    # Chronological holdout: train on first n_train days, score on last n_test days (separate model).
    holdout_r2: float | None = None
    holdout_mae: float | None = None
    holdout_n_train: int | None = None
    holdout_n_test: int | None = None


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


def _holdout_time_series_metrics(y: np.ndarray) -> tuple[float | None, float | None, int | None, int | None]:
    """Last chunk of days as test; train on prior days. Returns (r2, mae, n_train, n_test)."""
    n = len(y)
    n_test = max(2, min(14, n // 5))
    if n <= n_test + 2:
        return None, None, None, None
    n_train = n - n_test
    x_tr = np.arange(n_train, dtype=float).reshape(-1, 1)
    y_tr = y[:n_train]
    x_te = np.arange(n_train, n, dtype=float).reshape(-1, 1)
    y_te = y[n_train:]
    hold_model = LinearRegression()
    hold_model.fit(x_tr, y_tr)
    y_hat = hold_model.predict(x_te)
    mae_h = float(mean_absolute_error(y_te, y_hat))
    if len(y_te) >= 2:
        r2_h = float(r2_score(y_te, y_hat))
    else:
        r2_h = None
    return r2_h, mae_h, n_train, n_test


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
    y_fitted = model.predict(x)
    r2_in = float(r2_score(y, y_fitted))
    mae_in = float(mean_absolute_error(y, y_fitted))
    holdout_r2, holdout_mae, holdout_n_train, holdout_n_test = _holdout_time_series_metrics(y)

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
        r2_in_sample=r2_in,
        mae_in_sample=mae_in,
        chart_uses_train_test_split=False,
        holdout_r2=holdout_r2,
        holdout_mae=holdout_mae,
        holdout_n_train=holdout_n_train,
        holdout_n_test=holdout_n_test,
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
        "r2_in_sample": result.r2_in_sample,
        "mae_in_sample": result.mae_in_sample,
        "chart_uses_train_test_split": result.chart_uses_train_test_split,
        "holdout_r2": result.holdout_r2,
        "holdout_mae": result.holdout_mae,
        "holdout_n_train": result.holdout_n_train,
        "holdout_n_test": result.holdout_n_test,
    }
    if result.forecast_day_start is not None:
        payload["forecast_day_start"] = result.forecast_day_start.dt.strftime("%Y-%m-%d").tolist()
    if result.forecast_cost_usd is not None:
        payload["forecast_cost_usd"] = result.forecast_cost_usd.astype(float).tolist()
    return payload


def log_forecast_diagnostics(label: str, result: CostForecastResult) -> None:
    """Print forecast fit metrics to stdout (visible in the Streamlit server terminal)."""
    if not result.sufficient_data:
        print(f"[provectus forecast] {label}: insufficient history, no metrics.")
        return
    n = len(result.historical)
    print(f"[provectus forecast] {label}")
    print(f"  Daily points in series: {n}")
    print(
        "  Chart model: LinearRegression on ALL days (indices 0..n-1). "
        "No train/test split for the plotted forecast line."
    )
    print(f"  chart_uses_train_test_split: {result.chart_uses_train_test_split}")
    if result.r2_in_sample is not None:
        print(f"  In-sample R^2 (same data used to fit the chart model): {result.r2_in_sample:.6f}")
    if result.mae_in_sample is not None:
        print(f"  In-sample MAE USD (same data): {result.mae_in_sample:.6f}")
    if result.holdout_n_train is not None and result.holdout_n_test is not None:
        print(
            f"  Holdout check: separate model trained on first {result.holdout_n_train} days, "
            f"evaluated on last {result.holdout_n_test} days (chronological)."
        )
        if result.holdout_r2 is not None:
            print(f"  Holdout R^2: {result.holdout_r2:.6f}")
        if result.holdout_mae is not None:
            print(f"  Holdout MAE USD: {result.holdout_mae:.6f}")
    else:
        print("  Holdout check: skipped (not enough days for train+test split).")
