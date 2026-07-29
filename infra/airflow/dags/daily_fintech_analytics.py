"""
Daily fintech analytics pipeline (Phase 3).

  run_simulation -> dbt_run -> dbt_test

Logical date {{ ds }} is passed to the simulation CLI (YYYY-MM-DD).
Catchup fills missed days sequentially when Docker/Airflow restarts.
"""

from __future__ import annotations

from datetime import datetime

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator

# Airflow ownership starts here; earlier history was loaded manually (see docs/runbook.md).
DAG_START_DATE = datetime(2026, 5, 29)

REPO_ROOT = "/opt/fintech"
DBT_PROJECT = f"{REPO_ROOT}/dbt"
DBT_PROFILES = "/opt/airflow/dbt"

with DAG(
    dag_id="daily_fintech_analytics",
    description="Simulate one business day, build dbt marts, run dbt tests",
    start_date=DAG_START_DATE,
    schedule="@daily",
    catchup=True,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["fintech", "phase-3"],
    default_args={
        "owner": "fintech-analytics",
        "depends_on_past": True,
        "retries": 1,
    },
) as dag:
    run_simulation = BashOperator(
        task_id="run_simulation",
        bash_command=f"cd {REPO_ROOT} && python -m simulation --date {{{{ ds }}}}",
        depends_on_past=True,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {REPO_ROOT} && "
            f"dbt deps --project-dir {DBT_PROJECT} --profiles-dir {DBT_PROFILES} && "
            f"dbt run --project-dir {DBT_PROJECT} --profiles-dir {DBT_PROFILES}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"dbt test --project-dir {DBT_PROJECT} --profiles-dir {DBT_PROFILES}"
        ),
    )

    # Build the AI CFO report for the logical date and store it in Postgres for
    # the Streamlit page. Numbers are computed in Python; the LLM only writes the
    # narrative. Falls back to a deterministic narrative if the LLM is unavailable.
    generate_cfo_report = BashOperator(
        task_id="generate_cfo_report",
        bash_command=f"cd {REPO_ROOT} && python -m reporting.generate --date {{{{ ds }}}}",
        # New leaf task: no prior run exists for historical dates, so do not
        # inherit depends_on_past from default_args (would block scheduling).
        depends_on_past=False,
    )

    run_simulation >> dbt_run >> dbt_test >> generate_cfo_report
