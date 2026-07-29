# Phase 3 — Orchestration (Airflow + dbt)

**Parent brief:** See `../Analytics Project Summary - Fintech Simulation.docx`.

**Prerequisites:** Phase 1 raw generator and Postgres; **Phase 2b** complete (AI-ready marts + MetricFlow v1 metrics validated locally).

**Status (2026-06-20): Done.** `infra/docker-compose.yml` runs Postgres + Airflow 3.1.5 (LocalExecutor). The `daily_fintech_analytics` DAG runs the full chain `run_simulation → dbt_run → dbt_test → generate_cfo_report`, with catchup from 2026-05-29. The CFO task is now wired (no longer deferred) — see [phase-4](../phase-4/README.md) for the `reporting/` package it calls.

## Goal

Automate the **daily analytics pipeline** with **one simple Airflow DAG**: synthetic ingestion → dbt transforms → quality gates → optional CFO report generation. No DAG health monitoring UI in Streamlit (document orchestration in Phase 5 screenshots + runbook).

## What to build

| Piece | Purpose |
|-------|---------|
| **Airflow runtime** | Extend `infra/docker-compose.yml`: Postgres (exists) + Airflow webserver + scheduler |
| **Single daily DAG** | `daily_fintech_analytics` — linear task graph (see below) |
| **Connections / variables** | Postgres; optional `LLM_API_KEY` for CFO task |
| **Runbook** | Start/stop, backfill N days for portfolio demo, troubleshooting |

### Intended daily workflow (one DAG — preferred)

```text
daily_fintech_analytics
  1. run_simulation          (python -m simulation --date {{ ds }})
  2. dbt_run                 (dbt run --project-dir dbt --profiles-dir dbt)
  3. dbt_test                (dbt test …)
  4. generate_cfo_report     (BashOperator — python -m reporting.generate; deterministic narrative if no API key)
```

**Task order:** simulation **before** dbt; `dbt run` **before** `dbt test`.

**CFO task:** Keep in the **same DAG** as the last step (simplest). A separate CFO-only DAG is optional later if you need to re-run insights without ETL — not required for portfolio.

**Out of scope**

- Streamlit pipeline / DAG monitoring page
- DAG health APIs in the app
- Alerting / PagerDuty (optional retries on tasks only)
- LLM calls inside dbt

### Optional tasks (pick one approach)

- `dbt docs generate` — artifact for portfolio screenshot (lineage)
- Skip `dbt docs serve` in production DAG; document manual `dbt docs serve` for local dev

## Outputs / acceptance criteria

- KPI marts and semantic layer refresh automatically after successful run.
- Single path **raw → marts** without manual CLI for day-to-day operation.
- Backfill script or documented loop for **30–60 days** of demo data (Phase 5).
- Runbook section: Airflow compose, trigger DAG, read task logs.

## Tools (expected)

Airflow, dbt, PostgreSQL, Python, Docker Compose.

## Notes for agents

- Reuse Phase 1 CLI (`python -m simulation`); do not duplicate generator logic in DAG unless necessary.
- Mirror `.env.example` in Airflow connections (Postgres host, credentials).
- Phase 4 dashboard may show **data freshness** only: `max(effective_date)` from `mrt_company_daily_kpi` — no Airflow API required.
- For local iteration before Airflow, continue manual sim + dbt per `docs/runbook.md`.
- Windows: document Docker Desktop / WSL if path or volume issues arise.

## Handoff to Phase 4

After a green DAG run, Streamlit reads refreshed marts; AI CFO page shows latest stored report (from task 4 or on-demand generate in app).
