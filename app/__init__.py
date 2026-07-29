"""Streamlit app package.

Marked as a package so backend code (e.g. the ``reporting`` package run by
Airflow) can import shared, Streamlit-free modules such as
``app.services.ai_client`` via ``PYTHONPATH`` set to the repo root.
"""
