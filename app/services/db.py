"""Postgres access for Streamlit — reads analytics_dev marts only."""

import os

import pandas as pd
import psycopg2
import streamlit as st

ANALYTICS_SCHEMA = "analytics_dev"

_COMPANY_KPI_COLUMNS = """
    effective_date,
    active_users,
    gross_revenue_usd,
    net_revenue_usd,
    gross_deposits_usd,
    withdrawals_usd,
    net_flow_usd,
    withdrawal_ratio
"""


def postgres_dsn_parts() -> dict:
    """Connection settings (same env vars as dbt / simulation)."""
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "fintech"),
        "user": os.environ.get("POSTGRES_USER", "fintech"),
        "password": os.environ.get("POSTGRES_PASSWORD", "fintech_dev_change_me"),
    }


def enrich_company_kpi(df: pd.DataFrame) -> pd.DataFrame:
    """Add per-user metrics derived from base mart columns."""
    if df.empty:
        return df

    users = df["active_users"].replace(0, pd.NA)
    df = df.copy()
    df["net_revenue_per_user_usd"] = df["net_revenue_usd"] / users
    df["gross_deposit_per_user_usd"] = df["gross_deposits_usd"] / users
    return df


def aggregate_geo_revenue(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Roll up country-grain geo mart to region or return country rows."""
    if df.empty:
        return df

    if by == "country":
        return df.sort_values(["effective_date", "country_name"])

    return (
        df.groupby(["effective_date", "region"], as_index=False)["gross_revenue_usd"]
        .sum()
        .sort_values(["effective_date", "region"])
    )


@st.cache_data(ttl=300, show_spinner="Loading company KPIs…")
def load_company_daily_kpi() -> pd.DataFrame:
    """Daily executive KPI mart for the dashboard."""
    query = f"""
        SELECT {_COMPANY_KPI_COLUMNS}
        FROM {ANALYTICS_SCHEMA}.mrt_company_daily_kpi
        ORDER BY effective_date
    """
    with psycopg2.connect(**postgres_dsn_parts()) as conn:
        df = pd.read_sql_query(query, conn)
    return enrich_company_kpi(df)


@st.cache_data(ttl=300, show_spinner="Loading geo revenue…")
def load_geo_daily_revenue() -> pd.DataFrame:
    """Country-grain daily gross revenue with region (aggregate in the app)."""
    query = f"""
        SELECT
            effective_date,
            country_name,
            region,
            gross_revenue_usd
        FROM {ANALYTICS_SCHEMA}.mrt_geo_daily_revenue
        ORDER BY effective_date, country_name
    """
    try:
        with psycopg2.connect(**postgres_dsn_parts()) as conn:
            return pd.read_sql_query(query, conn)
    except Exception as exc:
        if "mrt_geo_daily_revenue" in str(exc) and "does not exist" in str(exc):
            return pd.DataFrame(
                columns=["effective_date", "country_name", "region", "gross_revenue_usd"]
            )
        raise
