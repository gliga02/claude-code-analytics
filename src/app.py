"""
Streamlit entry for the Claude Code Analytics Platform.

Management and Developer views are separate callables so future role checks
can wrap one view without restructuring the layout tree.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics import (
    FORECAST_INSUFFICIENT_MESSAGE,
    api_error_summary,
    fetch_events_analysis_dataframe,
    fetch_events_developer_dataframe,
    forecast_cost_by_practice,
    forecast_daily_total_cost,
    peak_usage_by_hour,
    peak_usage_by_weekday,
    tool_success_summary,
    usage_by_practice_level,
)
from database.session import create_engine_instance, create_session_factory, get_database_path

COLOR_BG = "#FBF3D1"
COLOR_TEXT = "#1B211A"
COLOR_SECONDARY = "#F9F8F6"


def compute_platform_metrics(df: pd.DataFrame) -> dict[str, int | float]:
    """High-level counts for Management KPI cards."""
    if df.empty:
        return {"event_count": 0, "total_cost_usd": 0.0, "distinct_users": 0}
    return {
        "event_count": int(len(df)),
        "total_cost_usd": float(df["cost_usd"].fillna(0).sum()),
        "distinct_users": int(df["user_email"].nunique()),
    }


def filter_developer_events(
    df: pd.DataFrame,
    event_names: list[str] | None,
    email_substring: str,
) -> pd.DataFrame:
    """Apply Developer view filters and return newest-first rows."""
    if df.empty:
        return df
    out = df.copy()
    if event_names:
        out = out[out["event_name"].isin(event_names)]
    sub = email_substring.strip().lower()
    if sub:
        out = out[out["user_email"].str.lower().str.contains(sub, na=False)]
    if "event_ts" in out.columns:
        out = out.sort_values("event_ts", ascending=False)
    return out


def _style_plotly(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        plot_bgcolor=COLOR_SECONDARY,
        paper_bgcolor=COLOR_BG,
        font_color=COLOR_TEXT,
        title_font_color=COLOR_TEXT,
        legend_font_color=COLOR_TEXT,
    )
    return fig


def _inject_theme_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT};
        }}
        section[data-testid="stSidebar"] {{
            background-color: {COLOR_SECONDARY};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_management_view(analysis_df: pd.DataFrame) -> None:
    """Business-oriented summaries: KPIs, trends, forecasts, timing."""
    st.header("Management overview")
    if analysis_df.empty:
        st.info("No events in the database. Load data with load_database() then refresh.")
        return

    metrics = compute_platform_metrics(analysis_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Events", f"{metrics['event_count']:,}")
    c2.metric("Total cost (USD)", f"{metrics['total_cost_usd']:.4f}")
    c3.metric("Distinct users", f"{metrics['distinct_users']:,}")

    st.subheader("Usage by practice and level")
    trends = usage_by_practice_level(analysis_df)
    if trends.empty:
        st.caption("No rows to aggregate.")
    else:
        fig_t = go.Figure(
            data=[
                go.Bar(
                    x=trends.apply(lambda r: f"{r['practice']} / {r['level']}", axis=1),
                    y=trends["total_cost_usd"],
                    marker_color=COLOR_TEXT,
                    name="Cost USD",
                )
            ]
        )
        fig_t.update_layout(xaxis_title="Practice / Level", yaxis_title="Total cost (USD)")
        st.plotly_chart(_style_plotly(fig_t), use_container_width=True)

        fig_k = go.Figure(
            data=[
                go.Bar(
                    x=trends.apply(lambda r: f"{r['practice']} / {r['level']}", axis=1),
                    y=trends["total_tokens"],
                    marker_color="#4a5d4a",
                    name="Tokens",
                )
            ]
        )
        fig_k.update_layout(xaxis_title="Practice / Level", yaxis_title="Total tokens")
        st.plotly_chart(_style_plotly(fig_k), use_container_width=True)

    st.subheader("Cost forecasts")
    total_fc = forecast_daily_total_cost(analysis_df)
    if total_fc.sufficient_data and total_fc.forecast_cost_usd is not None:
        hist = total_fc.historical.copy()
        hist["day"] = pd.to_datetime(hist["day"], utc=True)
        fx = go.Figure()
        fx.add_trace(
            go.Scatter(
                x=hist["day"],
                y=hist["cost_usd"],
                mode="lines+markers",
                name="History",
            )
        )
        f_days = pd.to_datetime(total_fc.forecast_day_start, utc=True)
        fx.add_trace(
            go.Scatter(
                x=f_days,
                y=total_fc.forecast_cost_usd,
                mode="lines+markers",
                name="Forecast (30 days)",
            )
        )
        fx.update_layout(xaxis_title="Day (UTC)", yaxis_title="Cost (USD)")
        st.plotly_chart(_style_plotly(fx), use_container_width=True)
    else:
        st.info(FORECAST_INSUFFICIENT_MESSAGE)

    st.subheader("Forecasts by practice")
    by_p = forecast_cost_by_practice(analysis_df)
    rows: list[dict[str, Any]] = []
    for practice, res in sorted(by_p.items()):
        rows.append(
            {
                "practice": practice,
                "ready": res.sufficient_data,
                "note": ""
                if res.sufficient_data
                else (res.insufficient_message or FORECAST_INSUFFICIENT_MESSAGE),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Peak usage (UTC)")
    col_a, col_b = st.columns(2)
    with col_a:
        ph = peak_usage_by_hour(analysis_df)
        if ph.empty:
            st.caption("No timestamps for hourly view.")
        else:
            fph = go.Figure(
                data=[go.Bar(x=ph["hour_utc"], y=ph["event_count"], marker_color=COLOR_TEXT)]
            )
            fph.update_layout(xaxis_title="Hour (UTC)", yaxis_title="Events")
            st.plotly_chart(_style_plotly(fph), use_container_width=True)
    with col_b:
        pw = peak_usage_by_weekday(analysis_df)
        if pw.empty:
            st.caption("No timestamps for weekday view.")
        else:
            fpw = go.Figure(
                data=[go.Bar(x=pw["weekday"], y=pw["event_count"], marker_color="#4a5d4a")]
            )
            fpw.update_layout(xaxis_title="Weekday (UTC)", yaxis_title="Events")
            st.plotly_chart(_style_plotly(fpw), use_container_width=True)


def render_developer_view(dev_df: pd.DataFrame) -> None:
    """Technical tables: filters, recent events, tool health, API errors."""
    st.header("Developer view")
    if dev_df.empty:
        st.info("No events in the database. Load data with load_database() then refresh.")
        return

    st.subheader("Filters")
    names = sorted({str(x) for x in dev_df["event_name"].dropna().unique()})
    pick = st.multiselect("Event names", options=names, default=[])
    email_q = st.text_input("User email contains", value="")

    filtered = filter_developer_events(dev_df, pick if pick else None, email_q)
    st.subheader("Matching events")
    st.caption(f"Showing {len(filtered)} rows (newest first).")
    show_cols = [
        c
        for c in [
            "event_ts",
            "user_email",
            "event_name",
            "body",
            "session_id",
            "cost_usd",
            "duration_ms",
            "tool_name",
            "tool_success",
            "error_detail",
            "model",
            "practice",
            "level",
        ]
        if c in filtered.columns
    ]
    st.dataframe(filtered[show_cols], use_container_width=True, hide_index=True)

    st.subheader("Tool results")
    st.dataframe(tool_success_summary(dev_df), use_container_width=True, hide_index=True)

    st.subheader("API errors")
    st.dataframe(api_error_summary(dev_df), use_container_width=True, hide_index=True)


@st.cache_data(ttl=120)
def _load_dataframes(_db_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    engine = create_engine_instance()
    SessionLocal = create_session_factory(engine)
    with SessionLocal() as session:
        analysis_df = fetch_events_analysis_dataframe(session)
        dev_df = fetch_events_developer_dataframe(session)
    return analysis_df, dev_df


def run_dashboard() -> None:
    st.set_page_config(
        page_title="Claude Code Analytics",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_theme_css()
    st.title("Claude Code Analytics Platform")

    db_path = get_database_path()
    if not Path(db_path).is_file():
        st.error(
            f"SQLite database not found at {db_path}. "
            "Set PROVECTUS_DATABASE_PATH or run load_database() after init_schema."
        )
        st.stop()

    if st.sidebar.button("Refresh cached data"):
        _load_dataframes.clear()

    view = st.sidebar.radio(
        "Navigation",
        options=("Management", "Developer"),
        index=0,
    )

    analysis_df, dev_df = _load_dataframes(str(db_path))

    if view == "Management":
        render_management_view(analysis_df)
    else:
        render_developer_view(dev_df)


def main() -> None:
    """Non-Streamlit entry; the dashboard is started via streamlit run."""
    pass


if __name__ == "__main__":
    run_dashboard()
