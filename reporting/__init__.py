"""AI CFO report package.

Streamlit-free backend that the Airflow daily task imports to build the
executive report: it reads ``analytics_dev`` marts, computes deltas / target
attainment / forecasts in Python, asks the LLM to write the narrative, renders
a Jinja2 HTML template, and stores the result in Postgres. The Streamlit page
only reads the stored HTML back via ``reporting.store``.
"""
