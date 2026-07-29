"""Plotly charts — each function builds one figure from a DataFrame."""

import pandas as pd
import plotly.express as px


def revenue_trend_chart(df: pd.DataFrame):
    """
    Example line chart: gross vs net revenue over time.

    Copy this pattern for more charts — change x, y, chart type (px.bar, px.area, …).
    Returns a Plotly figure; the page calls st.plotly_chart(fig, use_container_width=True).
    """
    plot_df = df.sort_values("effective_date")
    long_df = plot_df.melt(
        id_vars=["effective_date"],
        value_vars=["gross_revenue_usd", "net_revenue_usd"],
        var_name="metric",
        value_name="usd",
    )
    long_df["metric"] = long_df["metric"].str.replace("_usd", "").str.replace("_", " ").str.title()

    return px.line(
        long_df,
        x="effective_date",
        y="usd",
        color="metric",
        title="Revenue trend",
        labels={"effective_date": "Date", "usd": "USD", "metric": "Metric"},
    )
