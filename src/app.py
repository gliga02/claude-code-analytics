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
    log_forecast_diagnostics,
    peak_usage_by_hour,
    peak_usage_by_weekday,
    tool_success_summary,
    usage_by_practice_level,
)
from database.session import create_engine_instance, create_session_factory, get_database_path

# Dark, minimal UI (elevated surfaces, single cool accent)
COLOR_BG = "#0D1117"
COLOR_SURFACE = "#161B22"
COLOR_ELEVATED = "#21262D"
COLOR_TEXT = "#F0F6FC"
COLOR_MUTED = "#8B949E"
COLOR_BORDER = "#30363D"
COLOR_ACCENT = "#58A6FF"
COLOR_ACCENT_MUTED = "#79B8FF"

# Management "Usage" bar charts (practice / level)
COLOR_USAGE_BAR = "#0066FF"
COLOR_USAGE_BAR_HIGHLIGHT = "#E6B325"
COLOR_USAGE_TOP2 = "#FCD400"

# Streamlit's Plotly view can print the word "undefined" if title or legend title is null in JSON.
_PLOTLY_CHART_CONFIG: dict[str, bool] = {"displayModeBar": True, "displaylogo": False}


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


def _is_usage_highlight_practice_level(practice: object, level: object) -> bool:
    """Highlight bars for Frontend Engineering L6 and ML Engineering L5 (fake data roles)."""
    if pd.isna(practice) or pd.isna(level):
        return False
    p = str(practice).strip().lower()
    lv = str(level).strip().upper()
    if "frontend" in p and lv == "L6":
        return True
    if "ml" in p and "engineering" in p and lv == "L5":
        return True
    return False


def _usage_bar_colors_ranked(trends_sorted: pd.DataFrame) -> list[str]:
    """Top two bars (highest metric) use COLOR_USAGE_TOP2; bottom two match default bar color; optional role highlight."""
    n = len(trends_sorted)
    colors: list[str] = []
    for pos in range(n):
        row = trends_sorted.iloc[pos]
        in_top = pos < 2
        in_bottom = pos >= max(0, n - 2)
        if in_top and in_bottom and n <= 2:
            colors.append(COLOR_USAGE_TOP2)
        elif in_top:
            colors.append(COLOR_USAGE_TOP2)
        elif in_bottom:
            colors.append(COLOR_USAGE_BAR)
        elif _is_usage_highlight_practice_level(row["practice"], row["level"]):
            colors.append(COLOR_USAGE_BAR_HIGHLIGHT)
        else:
            colors.append(COLOR_USAGE_BAR)
    return colors


def _usage_x_category_labels(trends_sorted: pd.DataFrame) -> list[str]:
    return [f"{row['practice']}<br>{row['level']}" for _, row in trends_sorted.iterrows()]


def _append_usage_legend_top2_only(fig: go.Figure) -> None:
    """Single legend swatch for the two highest-usage bars (marker-only trace, not drawn on axes)."""
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=14, color=COLOR_USAGE_TOP2, symbol="square", line=dict(width=0)),
            name="Two highest usage",
            showlegend=True,
            hoverinfo="skip",
        )
    )


def _show_usage_bar_chart(fig: go.Figure, x_categories: list[str], tick_text: list[str]) -> None:
    """Style and render Usage bars with readable selective x tick labels."""
    _style_plotly(fig)
    fig.update_layout(showlegend=True)
    fig.update_xaxes(
        type="category",
        tickmode="array",
        tickvals=x_categories,
        ticktext=tick_text,
        tickangle=-38,
        automargin=True,
        tickfont=dict(size=12, color=COLOR_TEXT),
        title_font=dict(color=COLOR_MUTED, size=12),
    )
    kwargs: dict[str, Any] = {
        "figure_or_data": fig,
        "use_container_width": True,
        "config": _PLOTLY_CHART_CONFIG,
    }
    try:
        st.plotly_chart(**kwargs, theme=None)
    except TypeError:
        st.plotly_chart(**kwargs)


def _style_plotly(fig: go.Figure) -> go.Figure:
    grid = COLOR_BORDER
    fig.update_layout(
        title=dict(text=""),
        legend=dict(title=dict(text="")),
        plot_bgcolor=COLOR_ELEVATED,
        paper_bgcolor=COLOR_BG,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", size=13, color=COLOR_TEXT),
        legend_font_color=COLOR_MUTED,
        margin=dict(l=48, r=24, t=24, b=48),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor=grid,
            zeroline=False,
            tickfont=dict(color=COLOR_MUTED),
            title_font=dict(color=COLOR_MUTED, size=12),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=grid,
            zeroline=False,
            showline=False,
            tickfont=dict(color=COLOR_MUTED),
            title_font=dict(color=COLOR_MUTED, size=12),
        ),
    )
    return fig


def _show_plotly(fig: go.Figure) -> None:
    """Render Plotly with options that avoid blank 'undefined' labels in Streamlit."""
    kwargs: dict[str, Any] = {
        "figure_or_data": _style_plotly(fig),
        "use_container_width": True,
        "config": _PLOTLY_CHART_CONFIG,
    }
    try:
        st.plotly_chart(**kwargs, theme=None)
    except TypeError:
        st.plotly_chart(**kwargs)


def _inject_theme_css() -> None:
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT};
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            color-scheme: dark;
        }}
        header[data-testid="stHeader"] {{
            background-color: {COLOR_SURFACE} !important;
            background-image: none !important;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        header[data-testid="stHeader"] * {{
            color: {COLOR_TEXT} !important;
        }}
        header[data-testid="stHeader"] svg,
        header[data-testid="stHeader"] [data-testid="stIconMaterial"] {{
            color: {COLOR_TEXT} !important;
            fill: {COLOR_TEXT} !important;
        }}
        [data-testid="stToolbar"] {{
            background-color: {COLOR_SURFACE} !important;
        }}
        [data-testid="stDecoration"] {{
            background: {COLOR_SURFACE} !important;
        }}
        .main .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 3rem;
            max-width: 1080px;
        }}
        .main .stMarkdown, .main p, .main span, .main label {{
            color: {COLOR_TEXT};
        }}
        .main h1, .main h2 {{
            font-weight: 600;
            letter-spacing: -0.02em;
            color: {COLOR_TEXT};
        }}
        .main h2 {{
            font-size: 1.35rem;
            margin-top: 0.25rem;
            margin-bottom: 0.5rem;
        }}
        .main h3 {{
            font-size: 0.6875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: {COLOR_MUTED};
            margin-top: 1.75rem;
            margin-bottom: 0.65rem;
            padding-bottom: 0.35rem;
            border-bottom: 1px solid {COLOR_BORDER};
        }}
        [data-testid="stCaption"] {{
            color: {COLOR_MUTED} !important;
        }}
        div[data-testid="stAlert"] {{
            background-color: {COLOR_ELEVATED} !important;
            color: {COLOR_TEXT} !important;
            border: 1px solid {COLOR_BORDER} !important;
        }}
        div[data-testid="stAlert"] p, div[data-testid="stAlert"] div {{
            color: {COLOR_TEXT} !important;
        }}
        .sidebar-title {{
            font-weight: 600;
            font-size: 1rem;
            letter-spacing: -0.02em;
            color: {COLOR_TEXT};
            margin: 0 0 0.25rem 0;
        }}
        .sidebar-sub {{
            font-size: 0.75rem;
            color: {COLOR_MUTED};
            margin: 0 0 1.25rem 0;
            line-height: 1.4;
        }}
        section[data-testid="stSidebar"] {{
            background-color: {COLOR_SURFACE};
            border-right: 1px solid {COLOR_BORDER};
            color: {COLOR_TEXT};
        }}
        section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {{
            color: {COLOR_TEXT};
        }}
        section[data-testid="stSidebar"] label {{
            color: {COLOR_TEXT} !important;
        }}
        section[data-testid="stSidebar"] .stRadio label,
        section[data-testid="stSidebar"] .stRadio label p,
        section[data-testid="stSidebar"] .stRadio label span {{
            color: {COLOR_TEXT} !important;
        }}
        section[data-testid="stSidebar"] .stRadio > label > div:first-child {{
            background-color: {COLOR_ELEVATED} !important;
            border: 1px solid {COLOR_BORDER} !important;
            color: {COLOR_TEXT} !important;
        }}
        section[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] label {{
            background-color: {COLOR_ELEVATED} !important;
            border: 1px solid {COLOR_BORDER} !important;
            color: {COLOR_TEXT} !important;
        }}
        section[data-testid="stSidebar"] .stRadio [data-baseweb="radio"] label:hover {{
            border-color: {COLOR_ACCENT} !important;
        }}
        section[data-testid="stSidebar"] .stRadio input:checked + div label,
        section[data-testid="stSidebar"] .stRadio input:checked + label {{
            background-color: {COLOR_BG} !important;
            border-color: {COLOR_ACCENT} !important;
            color: {COLOR_TEXT} !important;
            box-shadow: 0 0 0 1px {COLOR_ACCENT};
        }}
        section[data-testid="stSidebar"] div[role="radiogroup"] {{
            background: transparent !important;
        }}
        section[data-testid="stSidebar"] .stMarkdown .sidebar-sub {{
            color: {COLOR_MUTED} !important;
        }}
        .sidebar-db-path {{
            font-size: 0.65rem;
            line-height: 1.35;
            color: {COLOR_MUTED};
            word-break: break-all;
            margin: 0 0 0.75rem 0;
        }}
        [data-testid="stMetric"] {{
            background: {COLOR_ELEVATED};
            border: 1px solid {COLOR_BORDER};
            border-radius: 12px;
            padding: 1rem 1.1rem;
        }}
        [data-testid="stMetricValue"] {{
            font-size: 1.35rem;
            font-weight: 600;
            color: {COLOR_TEXT};
        }}
        [data-testid="stMetricLabel"] {{
            font-size: 0.75rem;
            color: {COLOR_MUTED};
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}
        .stButton > button {{
            border-radius: 8px;
            border: 1px solid {COLOR_BORDER};
            background: {COLOR_ELEVATED};
            color: {COLOR_TEXT};
            font-weight: 500;
        }}
        .stButton > button:hover {{
            border-color: {COLOR_ACCENT};
            color: {COLOR_ACCENT};
            background: {COLOR_SURFACE} !important;
        }}
        .main .stTextInput input, .main .stTextInput textarea {{
            background-color: {COLOR_ELEVATED} !important;
            color: {COLOR_TEXT} !important;
            border-color: {COLOR_BORDER} !important;
        }}
        .main [data-baseweb="select"] > div {{
            background-color: {COLOR_ELEVATED} !important;
            border-color: {COLOR_BORDER} !important;
            color: {COLOR_TEXT} !important;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
        }}
        [data-testid="stHorizontalBlock"] {{
            gap: 0.5rem;
        }}
        iframe[title="streamlit_plotly_chart"] {{
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_management_view(analysis_df: pd.DataFrame) -> None:
    """Business-oriented summaries: KPIs, trends, forecasts, timing."""
    st.markdown("## Overview")
    if analysis_df.empty:
        st.info("No events in the database. Load data with load_database() then refresh.")
        return

    metrics = compute_platform_metrics(analysis_df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Events", f"{metrics['event_count']:,}")
    c2.metric("Total cost (USD)", f"{metrics['total_cost_usd']:.4f}")
    c3.metric("Distinct users", f"{metrics['distinct_users']:,}")

    st.subheader("Usage")
    trends = usage_by_practice_level(analysis_df)
    if trends.empty:
        st.caption("No rows to aggregate.")
    else:
        trends_cost = trends.sort_values("total_cost_usd", ascending=False).reset_index(drop=True)
        x_cat_c = _usage_x_category_labels(trends_cost)
        colors_c = _usage_bar_colors_ranked(trends_cost)
        fig_t = go.Figure(
            data=[
                go.Bar(
                    x=x_cat_c,
                    y=trends_cost["total_cost_usd"],
                    marker_color=colors_c,
                    marker_line_width=0,
                    name="Cost USD",
                    showlegend=False,
                )
            ]
        )
        fig_t.update_layout(xaxis_title="Practice / Level", yaxis_title="Total cost (USD)")
        _append_usage_legend_top2_only(fig_t)
        _show_usage_bar_chart(fig_t, x_cat_c, list(x_cat_c))

        trends_tok = trends.sort_values("total_tokens", ascending=False).reset_index(drop=True)
        x_cat_k = _usage_x_category_labels(trends_tok)
        colors_k = _usage_bar_colors_ranked(trends_tok)
        fig_k = go.Figure(
            data=[
                go.Bar(
                    x=x_cat_k,
                    y=trends_tok["total_tokens"],
                    marker_color=colors_k,
                    marker_line_width=0,
                    name="Tokens",
                    showlegend=False,
                )
            ]
        )
        fig_k.update_layout(xaxis_title="Practice / Level", yaxis_title="Total tokens")
        _append_usage_legend_top2_only(fig_k)
        _show_usage_bar_chart(fig_k, x_cat_k, list(x_cat_k))

    st.subheader("Forecasts")
    total_fc = forecast_daily_total_cost(analysis_df)
    log_forecast_diagnostics("daily_total_cost (Management chart)", total_fc)
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
                line=dict(color=COLOR_USAGE_BAR, width=2),
                marker=dict(size=6, color=COLOR_USAGE_BAR),
            )
        )
        f_days = pd.to_datetime(total_fc.forecast_day_start, utc=True)
        fx.add_trace(
            go.Scatter(
                x=f_days,
                y=total_fc.forecast_cost_usd,
                mode="lines",
                name="Next 30 days",
                line=dict(color=COLOR_USAGE_TOP2, width=2, dash="dash"),
            )
        )
        fx.update_layout(xaxis_title="Day (UTC)", yaxis_title="Cost (USD)")
        _show_plotly(fx)
    else:
        st.info(FORECAST_INSUFFICIENT_MESSAGE)

    st.subheader("By practice")
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

    st.subheader("Timing (UTC)")
    col_a, col_b = st.columns(2)
    with col_a:
        ph = peak_usage_by_hour(analysis_df)
        if ph.empty:
            st.caption("No timestamps for hourly view.")
        else:
            fph = go.Figure(
                data=[
                    go.Bar(
                        x=ph["hour_utc"],
                        y=ph["event_count"],
                        marker_color=COLOR_USAGE_BAR,
                        marker_line_width=0,
                        name="Events",
                    )
                ]
            )
            fph.update_layout(xaxis_title="Hour (UTC)", yaxis_title="Events")
            _show_plotly(fph)
    with col_b:
        pw = peak_usage_by_weekday(analysis_df)
        if pw.empty:
            st.caption("No timestamps for weekday view.")
        else:
            fpw = go.Figure(
                data=[
                    go.Bar(
                        x=pw["weekday"],
                        y=pw["event_count"],
                        marker_color=COLOR_USAGE_BAR,
                        marker_line_width=0,
                        name="Events",
                    )
                ]
            )
            fpw.update_layout(xaxis_title="Weekday (UTC)", yaxis_title="Events")
            _show_plotly(fpw)


def render_developer_view(dev_df: pd.DataFrame) -> None:
    """Technical tables: filters, recent events, tool health, API errors."""
    st.markdown("## Developer")
    if dev_df.empty:
        st.info("No events in the database. Load data with load_database() then refresh.")
        return

    st.subheader("Filter")
    names = sorted({str(x) for x in dev_df["event_name"].dropna().unique()})
    pick = st.multiselect("Event names", options=names, default=[])
    email_q = st.text_input("User email contains", value="")

    filtered = filter_developer_events(dev_df, pick if pick else None, email_q)
    st.subheader("Events")
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

    st.subheader("Tools")
    st.dataframe(tool_success_summary(dev_df), use_container_width=True, hide_index=True)

    st.subheader("Errors")
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
        page_title="Claude Analytics",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_theme_css()
    st.sidebar.markdown(
        f'<p class="sidebar-title">Claude Analytics</p>'
        f'<p class="sidebar-sub">Usage and operations</p>',
        unsafe_allow_html=True,
    )

    db_path = get_database_path()
    if not Path(db_path).is_file():
        st.error(
            f"SQLite database not found at {db_path}. "
            "Set PROVECTUS_DATABASE_PATH or run load_database() after init_schema."
        )
        st.stop()

    resolved_db = str(Path(db_path).resolve())
    st.sidebar.markdown(
        f'<p class="sidebar-db-path">Database<br/>{resolved_db}</p>',
        unsafe_allow_html=True,
    )

    if st.sidebar.button("Refresh data"):
        _load_dataframes.clear()

    view = st.sidebar.radio(
        "View",
        options=("Management", "Developer"),
        index=0,
    )

    analysis_df, dev_df = _load_dataframes(str(db_path))

    st.caption("Telemetry and cost")
    st.markdown("---")

    if view == "Management":
        render_management_view(analysis_df)
    else:
        render_developer_view(dev_df)


def main() -> None:
    """Non-Streamlit entry; the dashboard is started via streamlit run."""
    pass


if __name__ == "__main__":
    run_dashboard()
