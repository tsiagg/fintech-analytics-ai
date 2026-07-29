"""Tables — formatted st.dataframe views."""

import pandas as pd
import streamlit as st


def render_recent_kpi_table(df: pd.DataFrame, n_rows: int = 7) -> None:
    """
    Example table: last N days of company KPIs, newest first.

    Copy this pattern for more tables — filter, sort, rename columns, then st.dataframe.
    """
    display = (
        df.sort_values("effective_date", ascending=False)
        .head(n_rows)
        .rename(
            columns={
                "effective_date": "Date",
                "active_users": "Active users",
                "net_revenue_usd": "Net revenue (USD)",
                "gross_deposits_usd": "Deposits (USD)",
            }
        )
    )
    st.dataframe(display, use_container_width=True, hide_index=True)
