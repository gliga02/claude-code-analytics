"""Usage trends: cost and token totals by practice and level."""

from __future__ import annotations

import pandas as pd


def usage_by_practice_level(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate cost and token counts by employee practice and level (joined labels)."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "practice",
                "level",
                "total_cost_usd",
                "total_tokens",
                "event_count",
            ]
        )
    d = df.copy()
    for col in ("input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"):
        if col not in d.columns:
            d[col] = 0
    d["_tokens"] = (
        d["input_tokens"].fillna(0)
        + d["output_tokens"].fillna(0)
        + d["cache_creation_tokens"].fillna(0)
        + d["cache_read_tokens"].fillna(0)
    )
    d["_cost"] = d["cost_usd"].fillna(0.0)
    grouped = d.groupby(["practice", "level"], dropna=False).agg(
        total_cost_usd=("_cost", "sum"),
        total_tokens=("_tokens", "sum"),
        event_count=("_cost", "count"),
    )
    return grouped.reset_index().sort_values(["practice", "level"]).reset_index(drop=True)
