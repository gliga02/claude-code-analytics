"""Temporal usage patterns in UTC."""

from __future__ import annotations

import pandas as pd


def peak_usage_by_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Rank hours (UTC) by event volume and summed cost."""
    d = df.dropna(subset=["event_ts"]).copy()
    if d.empty:
        return pd.DataFrame(columns=["hour_utc", "event_count", "total_cost_usd"])
    d["event_dt"] = pd.to_datetime(d["event_ts"], utc=True)
    d["hour_utc"] = d["event_dt"].dt.hour
    d["_cost"] = d["cost_usd"].fillna(0.0)
    grouped = d.groupby("hour_utc").agg(
        event_count=("event_ts", "count"),
        total_cost_usd=("_cost", "sum"),
    )
    return grouped.reset_index().sort_values("event_count", ascending=False).reset_index(drop=True)


def peak_usage_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """Event counts and cost totals by weekday name (UTC), Monday-first order."""
    d = df.dropna(subset=["event_ts"]).copy()
    if d.empty:
        return pd.DataFrame(
            columns=["weekday", "weekday_order", "event_count", "total_cost_usd"]
        )
    d["event_dt"] = pd.to_datetime(d["event_ts"], utc=True)
    d["weekday_order"] = d["event_dt"].dt.dayofweek
    d["weekday"] = d["event_dt"].dt.day_name()
    d["_cost"] = d["cost_usd"].fillna(0.0)
    grouped = d.groupby(["weekday_order", "weekday"], as_index=False).agg(
        event_count=("event_ts", "count"),
        total_cost_usd=("_cost", "sum"),
    )
    return grouped.sort_values("weekday_order").reset_index(drop=True)
