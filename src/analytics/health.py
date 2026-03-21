"""Operational health: tool outcomes and API errors."""

from __future__ import annotations

import pandas as pd


def tool_success_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Counts and shares of tool_result rows by tool_success flag."""
    sub = df[df["event_name"] == "tool_result"]
    if sub.empty:
        return pd.DataFrame(columns=["tool_success", "event_count", "share_of_tool_results"])
    counts = sub["tool_success"].value_counts(dropna=False)
    total = int(counts.sum())
    out = counts.rename("event_count").reset_index()
    out.columns = ["tool_success", "event_count"]
    out["share_of_tool_results"] = out["event_count"] / float(total)
    return out


def api_error_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Group api_error events by error text, model, and status code."""
    sub = df[df["event_name"] == "api_error"]
    if sub.empty:
        return pd.DataFrame(columns=["error_detail", "model", "status_code", "event_count"])
    grouped = (
        sub.groupby(["error_detail", "model", "status_code"], dropna=False)
        .size()
        .reset_index(name="event_count")
    )
    return grouped.sort_values("event_count", ascending=False).reset_index(drop=True)
