"""KPI cards — one st.metric per headline number."""

import pandas as pd
import streamlit as st


def _latest_and_previous(df: pd.DataFrame) -> tuple[pd.Series, pd.Series | None]:
    """Sort by date and return the last two rows (for value + delta)."""
    sorted_df = df.sort_values("effective_date")
    latest = sorted_df.iloc[-1]
    previous = sorted_df.iloc[-2] if len(sorted_df) >= 2 else None
    return latest, previous


def render_net_revenue_metric(df: pd.DataFrame) -> None:
    """
    Example KPI card: net revenue for the latest day vs the prior day.

    Copy this pattern for more metrics — change label, column, and formatter.
    """
    latest, previous = _latest_and_previous(df)
    value = latest["net_revenue_usd"]
    delta = None if previous is None else value - previous["net_revenue_usd"]

    st.metric(
        label="Net revenue",
        value=f"${value:,.0f}",
        delta=f"${delta:,.0f}" if delta is not None else None,
        help="Sum of daily net trade revenue (gross revenue minus affiliate cost).",
    )
