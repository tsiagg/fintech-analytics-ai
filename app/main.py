"""
Fintech Analytics — Streamlit app (Phase 4).

Run from repo root (venv active):
  streamlit run app/main.py
"""

import sys
from pathlib import Path

import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parent.parent
_APP_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

st.set_page_config(
    page_title="Fintech Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Fintech Analytics")
st.caption("Executive analytics on the fintech warehouse — Phase 4 in progress")

st.markdown(
    """
    Use the sidebar to navigate:

    - **Data Spot Check** — full mart tables for manual validation
    - **Executive Dashboard** — KPI sparklines, weekly geo revenue, per-user trends
    - **BI Assistant** — reactive chat over governed MetricFlow metrics (needs OpenRouter key)
    - **AI CFO** — structured executive report (generated daily by Airflow)
    """
)

st.page_link("pages/0_Data_Spot_Check.py", label="Open Data Spot Check →", icon="🔍")
st.page_link("pages/1_Executive_Dashboard.py", label="Open Executive Dashboard →", icon="📈")
st.page_link("pages/2_BI_Assistant.py", label="Open BI Assistant →", icon="💬")
st.page_link("pages/3_AI_CFO.py", label="Open AI CFO →", icon="🧾")
