"""Parse telemetry JSONL batches into flattened event rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from ingestion.cleaning import (
    parse_cost_usd,
    parse_duration_ms,
    parse_iso_timestamp_utc,
    parse_optional_int,
    parse_tool_success,
)


def _inner_message_payload(raw_message: str) -> dict[str, Any]:
    try:
        parsed: Any = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError("logEvents.message is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("logEvents.message JSON must be an object")
    return parsed


def _row_from_log_event(log_event: dict[str, Any]) -> dict[str, Any] | None:
    raw_message = log_event.get("message")
    if raw_message is None or raw_message == "":
        return None
    if not isinstance(raw_message, str):
        raise TypeError("logEvents[].message must be a string")

    inner = _inner_message_payload(raw_message)
    body = inner.get("body")
    if body is not None and not isinstance(body, str):
        body = str(body)

    attrs = inner.get("attributes")
    if attrs is None:
        attrs = {}
    if not isinstance(attrs, dict):
        raise ValueError("message.attributes must be an object when present")

    resource = inner.get("resource")
    if resource is None:
        resource = {}
    if not isinstance(resource, dict):
        raise ValueError("message.resource must be an object when present")

    log_event_id = log_event.get("id")
    if log_event_id is not None:
        log_event_id = str(log_event_id)

    user_email_raw = attrs.get("user.email")
    user_email = str(user_email_raw).strip() if user_email_raw is not None else ""
    if not user_email:
        return None

    decision = attrs.get("decision")
    if decision is None:
        decision = attrs.get("decision_type")
    tool_decision: str | None
    if decision is None:
        tool_decision = None
    else:
        tool_decision = str(decision).strip() or None

    return {
        "log_event_id": log_event_id,
        "user_email": user_email,
        "event_ts": parse_iso_timestamp_utc(attrs.get("event.timestamp")),
        "session_id": attrs.get("session.id"),
        "body": body,
        "event_name": attrs.get("event.name"),
        "cost_usd": parse_cost_usd(attrs.get("cost_usd")),
        "duration_ms": parse_duration_ms(attrs.get("duration_ms")),
        "input_tokens": parse_optional_int(attrs.get("input_tokens")),
        "output_tokens": parse_optional_int(attrs.get("output_tokens")),
        "cache_creation_tokens": parse_optional_int(attrs.get("cache_creation_tokens")),
        "cache_read_tokens": parse_optional_int(attrs.get("cache_read_tokens")),
        "model": attrs.get("model"),
        "tool_name": attrs.get("tool_name"),
        "tool_success": parse_tool_success(attrs.get("success")),
        "tool_decision": tool_decision,
        "error_detail": attrs.get("error"),
        "status_code": attrs.get("status_code"),
        "resource_practice": resource.get("user.practice"),
    }


def iter_telemetry_rows(jsonl_path: Path) -> Iterator[dict[str, Any]]:
    """Yield flattened rows from telemetry_logs.jsonl (one top-level JSON object per line)."""
    if not jsonl_path.is_file():
        raise FileNotFoundError(f"Telemetry JSONL not found: {jsonl_path}")

    with jsonl_path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                batch: Any = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"telemetry_logs.jsonl line {line_no}: invalid JSON") from exc

            if not isinstance(batch, dict):
                raise ValueError(f"telemetry_logs.jsonl line {line_no}: root value must be an object")

            log_events = batch.get("logEvents")
            if log_events is None:
                continue
            if not isinstance(log_events, list):
                raise ValueError(f"telemetry_logs.jsonl line {line_no}: logEvents must be a list")

            for log_event in log_events:
                if not isinstance(log_event, dict):
                    continue
                row = _row_from_log_event(log_event)
                if row is not None:
                    yield row


def load_telemetry_dataframe(jsonl_path: Path) -> pd.DataFrame:
    """Load all telemetry rows into a DataFrame with stable column order."""
    rows = list(iter_telemetry_rows(jsonl_path))
    columns = [
        "log_event_id",
        "user_email",
        "event_ts",
        "session_id",
        "body",
        "event_name",
        "cost_usd",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "model",
        "tool_name",
        "tool_success",
        "tool_decision",
        "error_detail",
        "status_code",
        "resource_practice",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]
