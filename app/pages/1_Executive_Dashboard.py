"""Executive Dashboard — KPI sparklines and regional / per-user trends."""

import calendar
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from services.db import aggregate_geo_revenue, load_company_daily_kpi, load_geo_daily_revenue

REGIONS = ["America", "Europe", "Asia Pacific"]
COUNTRY_WEIGHTS: list[tuple[str, str, float]] = [
    ("United States", "America", 0.18),
    ("United Kingdom", "Europe", 0.11),
    ("Germany", "Europe", 0.10),
    ("France", "Europe", 0.09),
    ("Spain", "Europe", 0.07),
    ("Italy", "Europe", 0.07),
    ("Netherlands", "Europe", 0.08),
    ("Australia", "Asia Pacific", 0.08),
    ("Singapore", "Asia Pacific", 0.07),
    ("United Arab Emirates", "Asia Pacific", 0.08),
    ("Japan", "Asia Pacific", 0.07),
]

_SPARK_CONFIG = {"displayModeBar": False, "staticPlot": False}


def _mock_company_kpi() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    end = date.today()
    start = end - timedelta(days=89)
    dates = pd.date_range(start=start, end=end, freq="D")

    rows: list[dict] = []
    for d in dates:
        day_idx = (d - dates[0]).days
        season = 1.0 + 0.10 * np.sin(2 * np.pi * day_idx / 30)
        growth = 1.0 + 0.0012 * day_idx
        noise = rng.uniform(0.92, 1.08)

        active_users = int(12_500 * season * growth * rng.uniform(0.95, 1.05))
        gross_revenue_usd = round(145_000 * season * growth * noise, 2)
        net_revenue_usd = round(gross_revenue_usd * rng.uniform(0.78, 0.88), 2)
        gross_deposits_usd = round(520_000 * season * growth * noise, 2)
        withdrawals_usd = round(gross_deposits_usd * rng.uniform(0.32, 0.48), 2)
        net_flow_usd = round(gross_deposits_usd - withdrawals_usd, 2)
        withdrawal_ratio = (
            round(withdrawals_usd / gross_deposits_usd, 4) if gross_deposits_usd > 0 else None
        )

        rows.append(
            {
                "effective_date": d.date(),
                "active_users": active_users,
                "gross_revenue_usd": gross_revenue_usd,
                "net_revenue_usd": net_revenue_usd,
                "gross_deposits_usd": gross_deposits_usd,
                "withdrawals_usd": withdrawals_usd,
                "net_flow_usd": net_flow_usd,
                "withdrawal_ratio": withdrawal_ratio,
                "net_revenue_per_user_usd": round(net_revenue_usd / active_users, 2),
                "gross_deposit_per_user_usd": round(gross_deposits_usd / active_users, 2),
            }
        )

    return pd.DataFrame(rows)


def _mock_geo_revenue() -> pd.DataFrame:
    """Country-grain mock matching mrt_geo_daily_revenue."""
    company_df = _mock_company_kpi()
    rng = np.random.default_rng(99)
    rows: list[dict] = []

    for row in company_df.itertuples(index=False):
        countries = [c[0] for c in COUNTRY_WEIGHTS]
        jitter = {c: rng.uniform(0.92, 1.08) for c in countries}
        total_weight = sum(w * jitter[c] for c, _, w in COUNTRY_WEIGHTS)
        for country, region, weight in COUNTRY_WEIGHTS:
            share = (weight * jitter[country]) / total_weight
            rows.append(
                {
                    "effective_date": row.effective_date,
                    "country_name": country,
                    "region": region,
                    "gross_revenue_usd": round(row.gross_revenue_usd * share, 2),
                }
            )
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_company_kpi() -> pd.DataFrame:
    try:
        df = load_company_daily_kpi()
        if not df.empty:
            return df
    except Exception:
        pass
    return _mock_company_kpi()


@st.cache_data(ttl=300)
def load_geo_revenue() -> pd.DataFrame:
    try:
        df = load_geo_daily_revenue()
        if not df.empty:
            return df
    except Exception:
        pass
    return _mock_geo_revenue()


def clear_dashboard_data_cache() -> None:
    """Drop cached mart reads so the next render pulls fresh Postgres data."""
    load_company_kpi.clear()
    load_geo_revenue.clear()
    load_company_daily_kpi.clear()
    load_geo_daily_revenue.clear()


def daily_series(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    """One row per day — prevents duplicate-index chart bugs."""
    return (
        df.groupby("effective_date", as_index=False)[value_col]
        .sum()
        .sort_values("effective_date")
        .assign(effective_date=lambda d: pd.to_datetime(d["effective_date"]))
    )


def format_currency_compact(value: float) -> str:
    abs_val = abs(value)
    sign = "-" if value < 0 else ("+" if value > 0 else "")
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val / 1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val / 1_000:.0f}k"
    return f"{sign}${abs_val:,.0f}"


def parse_date_range(date_range) -> tuple[date, date]:
    if isinstance(date_range, tuple) and len(date_range) == 2:
        return date_range[0], date_range[1]
    single = date_range if not isinstance(date_range, tuple) else date_range[0]
    return single, single


def render_period_badge(
    current_fmt: str,
    prior_fmt: str,
    pct: float | None,
    period_label: str,
    prior_label: str,
) -> None:
    if pct is None:
        st.markdown(
            f"""<div style="background:rgba(108,117,125,0.10); border-left:4px solid #6c757d;
            padding:0.45rem 0.65rem; border-radius:4px; font-size:0.82rem; margin-top:0.35rem;">
            {period_label} <strong>{current_fmt}</strong> · no {prior_label} data
            </div>""",
            unsafe_allow_html=True,
        )
        return

    is_up = pct >= 0
    bg = "rgba(40,167,69,0.14)" if is_up else "rgba(220,53,69,0.14)"
    border = "#28a745" if is_up else "#dc3545"
    text = "#155724" if is_up else "#721c24"
    arrow = "▲" if is_up else "▼"

    st.markdown(
        f"""<div style="background:{bg}; border-left:4px solid {border};
        padding:0.45rem 0.65rem; border-radius:4px; font-size:0.82rem; margin-top:0.35rem;">
        <span style="color:{text}; font-weight:700;">{arrow} {abs(pct):.1f}%</span>
        <span style="color:#444;"> {prior_label}</span><br>
        <span style="color:#333;">{period_label} <strong>{current_fmt}</strong></span>
        <span style="color:#666;"> · Prior <strong>{prior_fmt}</strong></span>
        </div>""",
        unsafe_allow_html=True,
    )


def mtd_same_period_sum(
    df: pd.DataFrame, as_of: date, column: str
) -> tuple[float, float, float | None]:
    work = df.copy()
    work["_date"] = pd.to_datetime(work["effective_date"]).dt.date

    current_start = as_of.replace(day=1)
    current = work[(work["_date"] >= current_start) & (work["_date"] <= as_of)][column].sum()

    if as_of.month == 1:
        prior_start = date(as_of.year - 1, 12, 1)
        prior_last_day = calendar.monthrange(as_of.year - 1, 12)[1]
    else:
        prior_start = date(as_of.year, as_of.month - 1, 1)
        prior_last_day = calendar.monthrange(as_of.year, as_of.month - 1)[1]

    prior_end = date(prior_start.year, prior_start.month, min(as_of.day, prior_last_day))
    prior = work[(work["_date"] >= prior_start) & (work["_date"] <= prior_end)][column].sum()

    if prior == 0:
        return current, prior, None
    return current, prior, (current - prior) / prior * 100


def mtd_same_period_net_revenue(df: pd.DataFrame, as_of: date) -> tuple[float, float, float | None]:
    return mtd_same_period_sum(df, as_of, "net_revenue_usd")


def render_mtd_comparison(df: pd.DataFrame, as_of: date) -> None:
    current, prior, pct = mtd_same_period_net_revenue(df, as_of)
    render_period_badge(
        format_currency_compact(current).lstrip("+"),
        format_currency_compact(prior).lstrip("+"),
        pct,
        period_label="MTD",
        prior_label="vs prior month (same days)",
    )


def render_mtd_net_flow(df: pd.DataFrame, as_of: date) -> None:
    current, prior, pct = mtd_same_period_sum(df, as_of, "net_flow_usd")
    render_period_badge(
        format_currency_compact(current).lstrip("+"),
        format_currency_compact(prior).lstrip("+"),
        pct,
        period_label="MTD",
        prior_label="vs prior month (same days)",
    )


def wow_period_avg(
    df: pd.DataFrame, as_of: date, column: str
) -> tuple[float, float, float | None]:
    """Mean of a daily metric — last 7 days vs the prior 7 days."""
    work = df.copy()
    work["_date"] = pd.to_datetime(work["effective_date"]).dt.date

    current_start = as_of - timedelta(days=6)
    prior_end = current_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=6)

    current_avg = work[(work["_date"] >= current_start) & (work["_date"] <= as_of)][column].mean()
    prior_avg = work[(work["_date"] >= prior_start) & (work["_date"] <= prior_end)][column].mean()

    if pd.isna(current_avg) or pd.isna(prior_avg) or prior_avg == 0:
        return current_avg or 0, prior_avg or 0, None
    return current_avg, prior_avg, (current_avg - prior_avg) / prior_avg * 100


def wow_active_users(df: pd.DataFrame, as_of: date) -> tuple[float, float, float | None]:
    return wow_period_avg(df, as_of, "active_users")


def render_wow_active_users(df: pd.DataFrame, as_of: date) -> None:
    current, prior, pct = wow_active_users(df, as_of)
    render_period_badge(
        f"{current:,.0f}",
        f"{prior:,.0f}",
        pct,
        period_label="This week avg",
        prior_label="WoW vs prior week",
    )


def render_wow_withdrawal_ratio(df: pd.DataFrame, as_of: date) -> None:
    current, prior, pct = wow_period_avg(df, as_of, "withdrawal_ratio")
    if pd.isna(current) and pd.isna(prior):
        render_period_badge("—", "—", None, period_label="This week avg", prior_label="WoW vs prior week")
        return
    render_period_badge(
        f"{current * 100:.1f}%",
        f"{prior * 100:.1f}%",
        pct,
        period_label="This week avg",
        prior_label="WoW vs prior week",
    )


def aggregate_geo_weekly(df: pd.DataFrame, dimension_col: str) -> pd.DataFrame:
    """Roll daily geo revenue up to calendar weeks (Mon start) with revenue share."""
    geo = df.copy()
    geo["effective_date"] = pd.to_datetime(geo["effective_date"])
    geo["week_start"] = geo["effective_date"].dt.to_period("W-MON").dt.start_time

    weekly = (
        geo.groupby(["week_start", dimension_col], as_index=False)["gross_revenue_usd"]
        .sum()
        .sort_values(["week_start", dimension_col])
    )
    weekly["week_total"] = weekly.groupby("week_start")["gross_revenue_usd"].transform("sum")
    weekly["revenue_share_pct"] = np.where(
        weekly["week_total"] > 0,
        weekly["gross_revenue_usd"] / weekly["week_total"] * 100,
        0,
    )
    return weekly


def geo_revenue_weekly_chart(
    weekly_df: pd.DataFrame,
    dimension_col: str,
    chart_title: str,
    category_orders: dict | None,
) -> go.Figure:
    fig = px.bar(
        weekly_df,
        x="week_start",
        y="gross_revenue_usd",
        color=dimension_col,
        title=chart_title,
        labels={
            "week_start": "Week starting",
            "gross_revenue_usd": "Gross Revenue (USD)",
            dimension_col: dimension_col.replace("_", " ").title(),
        },
        category_orders=category_orders,
        custom_data=["revenue_share_pct"],
    )
    fig.update_traces(
        hovertemplate=(
            "Week of %{x|%b %d, %Y}<br>"
            "%{fullData.name}<br>"
            "$%{y:,.0f} · %{customdata[0]:.1f}% of week<extra></extra>"
        )
    )
    fig.update_layout(
        barmode="stack",
        margin=dict(l=0, r=0, t=40, b=0),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def add_extreme_markers(
    fig: go.Figure,
    plot_df: pd.DataFrame,
    x_col: str,
    y_col: str,
    hover_fmt: str = "$%{y:,.2f}",
    marker_size: int = 8,
) -> go.Figure:
    """Green dot at series max, red dot at series min."""
    if plot_df.empty:
        return fig

    idx_max = plot_df[y_col].idxmax()
    idx_min = plot_df[y_col].idxmin()
    max_row = plot_df.loc[idx_max]
    min_row = plot_df.loc[idx_min]

    fig.add_trace(
        go.Scatter(
            x=[max_row[x_col]],
            y=[max_row[y_col]],
            mode="markers",
            name="High",
            marker=dict(size=marker_size, color="#28a745", line=dict(width=1.5, color="white")),
            hovertemplate=f"%{{x|%b %d, %Y}}<br>High: {hover_fmt}<extra></extra>",
            showlegend=False,
        )
    )
    if idx_min != idx_max:
        fig.add_trace(
            go.Scatter(
                x=[min_row[x_col]],
                y=[min_row[y_col]],
                mode="markers",
                name="Low",
                marker=dict(size=marker_size, color="#dc3545", line=dict(width=1.5, color="white")),
                hovertemplate=f"%{{x|%b %d, %Y}}<br>Low: {hover_fmt}<extra></extra>",
                showlegend=False,
            )
        )
    return fig


def per_user_line_chart(
    df: pd.DataFrame,
    y_col: str,
    title: str,
    hover_fmt: str = "$%{y:,.2f}",
) -> go.Figure:
    plot_df = daily_series(df, y_col)
    fig = px.line(
        plot_df,
        x="effective_date",
        y=y_col,
        title=title,
        labels={"effective_date": "Date", y_col: "USD per User"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), hovermode="x unified")
    add_extreme_markers(fig, plot_df, "effective_date", y_col, hover_fmt=hover_fmt)
    return fig


def sparkline(df: pd.DataFrame, value_col: str, hover_fmt: str = "$%{y:,.0f}") -> None:
    """Plotly mini-chart — daily values only."""
    plot_df = daily_series(df, value_col)
    if plot_df.empty:
        return

    fig = go.Figure(
        go.Scatter(
            x=plot_df["effective_date"],
            y=plot_df[value_col],
            mode="lines",
            fill="tozeroy",
            line=dict(width=2),
            hovertemplate=f"%{{x|%b %d, %Y}}<br>{hover_fmt}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=90,
        margin=dict(l=4, r=4, t=4, b=4),
        showlegend=False,
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
    )
    st.plotly_chart(fig, use_container_width=True, config=_SPARK_CONFIG)


def kpi_card(
    label: str,
    value: str,
    df: pd.DataFrame,
    value_col: str,
    hover_fmt: str = "$%{y:,.0f}",
    **metric_kwargs,
) -> None:
    st.metric(label, value, **metric_kwargs)
    sparkline(df, value_col, hover_fmt=hover_fmt)


# --- Page ---

header_left, header_right = st.columns([6, 1])
with header_left:
    st.title("Executive Dashboard")
    st.caption("Sources: `mrt_company_daily_kpi`, `mrt_geo_daily_revenue`")
with header_right:
    st.write("")
    if st.button(
        "Refresh data",
        use_container_width=True,
        help="Reload marts from Postgres after simulation or dbt run.",
    ):
        clear_dashboard_data_cache()
        st.session_state.pop("exec_dashboard_date_range", None)
        st.rerun()

kpi_df = load_company_kpi()

min_date = pd.to_datetime(kpi_df["effective_date"]).min().date()
max_date = pd.to_datetime(kpi_df["effective_date"]).max().date()
default_range = (max(max_date - timedelta(days=29), min_date), max_date)

date_range = st.date_input(
    "Date range",
    value=default_range,
    min_value=min_date,
    max_value=max_date,
    key="exec_dashboard_date_range",
)
st.caption(f"Warehouse data through **{max_date:%Y-%m-%d}**.")

start_date, end_date = parse_date_range(date_range)
filtered_kpi = kpi_df[
    (pd.to_datetime(kpi_df["effective_date"]).dt.date >= start_date)
    & (pd.to_datetime(kpi_df["effective_date"]).dt.date <= end_date)
].copy()

if filtered_kpi.empty:
    st.info("No data available for the selected filters.")
    st.stop()

net_revenue = filtered_kpi["net_revenue_usd"].sum()
avg_active_users = filtered_kpi["active_users"].mean()
net_flow = filtered_kpi["net_flow_usd"].sum()
avg_withdrawal_ratio = filtered_kpi["withdrawal_ratio"].mean()

kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    kpi_card(
        "Net Revenue",
        format_currency_compact(net_revenue).lstrip("+"),
        filtered_kpi,
        "net_revenue_usd",
    )
    render_mtd_comparison(kpi_df, end_date)

with kpi2:
    kpi_card(
        "Active Users",
        f"{avg_active_users:,.0f}",
        filtered_kpi,
        "active_users",
        hover_fmt="%{y:,.0f}",
    )
    render_wow_active_users(kpi_df, end_date)

with kpi3:
    kpi_card(
        "Net Flow (Deposits)",
        format_currency_compact(net_flow).lstrip("+"),
        filtered_kpi,
        "net_flow_usd",
    )
    render_mtd_net_flow(kpi_df, end_date)

with kpi4:
    ratio_display = "—" if pd.isna(avg_withdrawal_ratio) else f"{avg_withdrawal_ratio * 100:.1f}%"
    ratio_df = filtered_kpi.assign(withdrawal_ratio_pct=filtered_kpi["withdrawal_ratio"] * 100)
    kpi_card(
        "Withdrawal Ratio",
        ratio_display,
        ratio_df,
        "withdrawal_ratio_pct",
        hover_fmt="%{y:.1f}%",
    )
    render_wow_withdrawal_ratio(kpi_df, end_date)

st.divider()

geo_breakdown = st.segmented_control(
    "Revenue breakdown",
    options=["Region", "Country"],
    default="Region",
    selection_mode="single",
)

dimension = "region" if geo_breakdown == "Region" else "country"
geo_base = load_geo_revenue()
geo_base = geo_base[
    (pd.to_datetime(geo_base["effective_date"]).dt.date >= start_date)
    & (pd.to_datetime(geo_base["effective_date"]).dt.date <= end_date)
]
geo_df = aggregate_geo_revenue(geo_base, dimension)

color_col = "region" if dimension == "region" else "country_name"
chart_title = (
    f"Gross Revenue by {geo_breakdown} (Weekly)"
)

if geo_df.empty:
    st.info(f"No {dimension} data available for the selected filters.")
else:
    weekly_geo = aggregate_geo_weekly(geo_df, color_col)
    category_orders = {"region": REGIONS} if dimension == "region" else None
    regional_fig = geo_revenue_weekly_chart(
        weekly_geo,
        color_col,
        chart_title,
        category_orders,
    )
    st.plotly_chart(regional_fig, use_container_width=True)

per_user_left, per_user_right = st.columns(2)

revenue_per_user_fig = per_user_line_chart(
    filtered_kpi,
    "net_revenue_per_user_usd",
    "Net Revenue per Active User",
)

deposit_per_user_fig = per_user_line_chart(
    filtered_kpi,
    "gross_deposit_per_user_usd",
    "Gross Deposit per Active User",
)

with per_user_left:
    st.plotly_chart(revenue_per_user_fig, use_container_width=True)

with per_user_right:
    st.plotly_chart(deposit_per_user_fig, use_container_width=True)
