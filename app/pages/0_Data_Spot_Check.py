"""Data spot-check tables for validating mrt_company_daily_kpi and geo revenue."""

import sys
from datetime import timedelta
from pathlib import Path

import streamlit as st

_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from services.db import aggregate_geo_revenue, load_company_daily_kpi, load_geo_daily_revenue

st.title("Data Spot Check")
st.caption("Raw mart rows for manual validation · `mrt_company_daily_kpi` · `mrt_geo_daily_revenue`")

try:
    company_df = load_company_daily_kpi()
    geo_df = load_geo_daily_revenue()
except Exception as exc:
    st.error(f"Could not connect to Postgres: {exc}")
    st.info(
        "Start Postgres (`docker compose -f infra/docker-compose.yml up -d`) and run "
        "`dbt run --select mrt_company_daily_kpi mrt_geo_daily_revenue`."
    )
    st.stop()

if company_df.empty:
    st.warning("Connected, but `mrt_company_daily_kpi` has no rows yet.")
    st.stop()

min_date = company_df["effective_date"].min()
max_date = company_df["effective_date"].max()

date_range = st.date_input(
    "Date range",
    value=(max_date - timedelta(days=29), max_date),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = end_date = date_range if not isinstance(date_range, tuple) else date_range[0]

filtered_company = company_df[
    (company_df["effective_date"] >= start_date) & (company_df["effective_date"] <= end_date)
].sort_values("effective_date", ascending=False)

filtered_geo = geo_df[
    (geo_df["effective_date"] >= start_date) & (geo_df["effective_date"] <= end_date)
].sort_values(["effective_date", "country_name"], ascending=[False, True])

st.caption(f"Showing **{len(filtered_company):,}** company days · data through **{max_date}**")

st.subheader("Company daily KPI")
st.dataframe(
    filtered_company,
    use_container_width=True,
    hide_index=True,
    column_config={
        "effective_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
        "active_users": st.column_config.NumberColumn("Active users", format="%d"),
        "gross_revenue_usd": st.column_config.NumberColumn("Gross revenue", format="$%.2f"),
        "net_revenue_usd": st.column_config.NumberColumn("Net revenue", format="$%.2f"),
        "gross_deposits_usd": st.column_config.NumberColumn("Gross deposits", format="$%.2f"),
        "withdrawals_usd": st.column_config.NumberColumn("Withdrawals", format="$%.2f"),
        "net_flow_usd": st.column_config.NumberColumn("Net flow", format="$%.2f"),
        "withdrawal_ratio": st.column_config.NumberColumn("Withdrawal ratio", format="%.2%%"),
        "net_revenue_per_user_usd": st.column_config.NumberColumn("Net rev / user", format="$%.2f"),
        "gross_deposit_per_user_usd": st.column_config.NumberColumn("Deposit / user", format="$%.2f"),
    },
    column_order=[
        "effective_date",
        "active_users",
        "gross_revenue_usd",
        "net_revenue_usd",
        "gross_deposits_usd",
        "withdrawals_usd",
        "net_flow_usd",
        "withdrawal_ratio",
        "net_revenue_per_user_usd",
        "gross_deposit_per_user_usd",
    ],
)

st.subheader("Geo daily revenue (country grain)")
if filtered_geo.empty:
    st.info(
        "No geo rows for this range. Run "
        "`dbt run --select mrt_geo_daily_revenue` if the mart is missing."
    )
else:
    st.dataframe(
        filtered_geo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "effective_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "country_name": st.column_config.TextColumn("Country"),
            "region": st.column_config.TextColumn("Region"),
            "gross_revenue_usd": st.column_config.NumberColumn("Gross revenue", format="$%.2f"),
        },
    )

    st.subheader("Geo daily revenue (aggregated to region)")
    regional_view = aggregate_geo_revenue(filtered_geo, "region")
    st.dataframe(
        regional_view.sort_values(["effective_date", "region"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "effective_date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
            "region": st.column_config.TextColumn("Region"),
            "gross_revenue_usd": st.column_config.NumberColumn("Gross revenue", format="$%.2f"),
        },
    )

with st.expander("Export"):
    st.download_button(
        "Download company KPI (CSV)",
        filtered_company.to_csv(index=False).encode("utf-8"),
        file_name="mrt_company_daily_kpi.csv",
        mime="text/csv",
    )
    if not filtered_geo.empty:
        st.download_button(
            "Download geo revenue (CSV)",
            filtered_geo.to_csv(index=False).encode("utf-8"),
            file_name="mrt_geo_daily_revenue.csv",
            mime="text/csv",
        )
