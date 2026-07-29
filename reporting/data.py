"""Postgres access for the AI CFO report.

Streamlit-free on purpose: this module is imported by the Airflow task (which
has no Streamlit), so it mirrors the connection settings from
``app/services/db.py`` without the ``st.cache_data`` decorators. It reads only
the governed ``analytics_dev`` marts.
"""

from __future__ import annotations

import os

import pandas as pd
import psycopg2

ANALYTICS_SCHEMA = "analytics_dev"


def postgres_dsn_parts() -> dict:
    """Connection settings (same env vars as dbt / simulation / the app)."""
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", "5432")),
        "dbname": os.environ.get("POSTGRES_DB", "fintech"),
        "user": os.environ.get("POSTGRES_USER", "fintech"),
        "password": os.environ.get("POSTGRES_PASSWORD", "fintech_dev_change_me"),
    }


def _read_sql(query: str) -> pd.DataFrame:
    with psycopg2.connect(**postgres_dsn_parts()) as conn:
        return pd.read_sql_query(query, conn)


def load_company_daily_kpi() -> pd.DataFrame:
    """Daily company KPI mart. SELECT * so a newly added ``new_users`` column is
    picked up automatically once the dbt model ships, without a code change."""
    query = f"""
        SELECT *
        FROM {ANALYTICS_SCHEMA}.mrt_company_daily_kpi
        ORDER BY effective_date
    """
    df = _read_sql(query)
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
    return df


def load_geo_daily_revenue() -> pd.DataFrame:
    """Country-grain daily gross revenue with region."""
    query = f"""
        SELECT effective_date, country_name, region, gross_revenue_usd
        FROM {ANALYTICS_SCHEMA}.mrt_geo_daily_revenue
        ORDER BY effective_date, country_name
    """
    df = _read_sql(query)
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
    return df


def load_instrument_daily_kpi() -> pd.DataFrame:
    """Instrument-grain daily KPIs (cost, cashback, revenue) by symbol/group."""
    query = f"""
        SELECT
            effective_date,
            region,
            symbol_name,
            symbol_nickname,
            symbol_group,
            company_pnl_usd,
            trade_cost_usd,
            cashback_usd,
            trade_revenue_usd
        FROM {ANALYTICS_SCHEMA}.mrt_instrument_daily_kpi
        ORDER BY effective_date
    """
    df = _read_sql(query)
    if not df.empty:
        df["effective_date"] = pd.to_datetime(df["effective_date"])
    return df


def load_monthly_performance() -> pd.DataFrame:
    """Region-grain monthly actual vs target (the only three seed targets)."""
    query = f"""
        SELECT
            region,
            effective_month,
            actual_active_users,
            target_active_users,
            actual_net_trade_revenue_usd,
            target_net_trade_revenue_usd,
            actual_gross_deposit_usd,
            target_gross_deposit_usd
        FROM {ANALYTICS_SCHEMA}.mrt_company_monthly_performance
        ORDER BY effective_month, region
    """
    df = _read_sql(query)
    if not df.empty:
        df["effective_month"] = pd.to_datetime(df["effective_month"])
    return df


def get_data_date_range() -> tuple[str | None, str | None]:
    """Min/max effective_date in the company KPI mart."""
    query = (
        "SELECT MIN(effective_date)::text, MAX(effective_date)::text "
        f"FROM {ANALYTICS_SCHEMA}.mrt_company_daily_kpi"
    )
    try:
        with psycopg2.connect(**postgres_dsn_parts()) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)
    except Exception:
        return (None, None)
