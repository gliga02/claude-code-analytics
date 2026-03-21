"""Coerce telemetry strings and numbers for analytics and loading."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def parse_iso_timestamp_utc(value: Any) -> datetime | None:
    """Parse OpenTelemetry-style ISO timestamps, including Z suffix."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    normalized = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_cost_usd(value: Any) -> float | None:
    """Parse cost_usd; return None for missing or non-numeric values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return float(value)
    if isinstance(value, int):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_duration_ms(value: Any) -> int | None:
    """Parse duration_ms as integer milliseconds; round floats safely."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(round(value))
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def parse_optional_int(value: Any) -> int | None:
    """Parse optional integer token counts and similar fields."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_tool_success(value: Any) -> bool | None:
    """Parse telemetry success strings such as true or false."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s == "true":
        return True
    if s == "false":
        return False
    return None
