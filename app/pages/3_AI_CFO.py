"""AI CFO Report - displays the latest report produced by the Airflow task.

This page is read-only: the report is generated daily by the
``generate_cfo_report`` task in the Airflow DAG (numbers computed in Python, the
LLM writes the narrative, a Jinja2 template is rendered to HTML and stored in
Postgres). Here we just fetch the most recent stored HTML and embed it.
"""

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from reporting import store

st.set_page_config(page_title="AI CFO", page_icon="🧾", layout="wide")

st.title("AI CFO Report")
st.caption(
    "A proactive executive report generated after the daily pipeline run. "
    "All figures are computed in the warehouse; the model only writes the narrative. "
    "After a DAG run completes, click **Refresh report** or press **R** in the browser "
    "to load the latest row from Postgres."
)

col_refresh, col_download, _ = st.columns([1, 1, 4])

with col_refresh:
    if st.button("Refresh report", type="primary", use_container_width=True):
        st.rerun()

try:
    row = store.fetch_latest()
except Exception as exc:  # noqa: BLE001 - surface any store error in the UI
    st.error(f"Could not read the report store: {exc}")
    st.stop()

if not row:
    st.info(
        "No CFO report has been generated yet.\n\n"
        "Generate one by running the Airflow DAG "
        "(`daily_fintech_analytics` -> `generate_cfo_report`), or locally with:\n\n"
        "```\npython -m reporting.generate --date YYYY-MM-DD\n```"
    )
    st.stop()

tokens = (row.get("prompt_tokens") or 0) + (row.get("completion_tokens") or 0)
st.caption(
    f"Report id **{row.get('id')}** — stored in `analytics_dev.cfo_report_runs` — "
    f"generated {row.get('generated_at')} — "
    f"model {row.get('model')} — {tokens} tokens — "
    f"period {row.get('period_start')} → {row.get('period_end')}"
)

report_html = row["report_html"]
report_date = row.get("report_date")
file_stamp = report_date.isoformat() if hasattr(report_date, "isoformat") else "latest"
with col_download:
    st.download_button(
        label="⬇ Download (HTML)",
        data=report_html.encode("utf-8"),
        file_name=f"cfo_report_{file_stamp}.html",
        mime="text/html",
        use_container_width=True,
        help=(
            "Downloads this exact report as a self-contained, styled HTML file you can "
            "share or archive. To save as PDF, open the file in your browser and use "
            "Print → Save as PDF."
        ),
    )

components.html(report_html, height=1600, scrolling=True)
