---
title: File guide
parent: Thinking
nav_order: 3
---

# File guide

The repository contains more than 100 tracked files. Around fifteen carry most of the signal for a reviewer. This page explains which ones to open and why.

## If you have five minutes

Open these three, in this order:

1. **[`dbt/models/intermediate/int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql)** — the business logic that makes the rest meaningful. Trading cost per lot, cashback uplifted for VIP clients on a sliding scale by instrument group, and revenue assembled from company PnL plus cost minus cashback.
2. **[`dbt/models/semantic_models/metrics.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/semantic_models/metrics.yml)** — 57 metrics. Skim for the mix of simple, ratio, cumulative and derived types rather than reading it all.
3. **[`app/services/metrics.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/app/services/metrics.py)** — the gate every AI-planned query passes through before it is allowed to run.

## My analytics engineering work

This is the part I would defend line by line.

- **[`dbt/models/marts/mrt_daily_user_activity.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/mrt_daily_user_activity.sql)** — the core mart at user by day grain, and where acquisition cost gets netted off revenue.
- **[`dbt/models/marts/marts.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/marts.yml)** — the documentation and grain tests. Read this alongside the SQL; it is where the claims about each model are made and enforced.
- **[`dbt/models/serving/streamlit_dashboard/mrt_company_daily_kpi.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/serving/streamlit_dashboard/mrt_company_daily_kpi.sql)** — short, and worth it for two details: the null-guarded withdrawal ratio, and new users counted off the signup date rather than the activity spine so a signup-only day still registers.
- **[`dbt/models/semantic_models/semantic_users_daily.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/semantic_models/semantic_users_daily.yml)** — entities, dimensions and the ten measures the metrics are built from.
- **[`dbt/dbt_project.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/dbt_project.yml)** — the materialization strategy in a dozen lines: views for thin layers, tables for anything read repeatedly.
- **[`dbt/seeds/region_monthly_targets.csv`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/seeds/region_monthly_targets.csv)** — the plan that every variance and attainment metric is measured against.

## Architecture I directed, agent implemented

Worth reading for the design; the implementation is not mine to claim.

- **[`app/services/semantic.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/app/services/semantic.py)** — builds the metric allowlist by parsing the same YAML dbt uses, so the two cannot drift.
- **[`reporting/forecasting.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/forecasting.py)** and **[`reporting/anomalies.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/anomalies.py)** — around 120 lines each. Small enough to verify at a glance, which is the point: the month-end projection and the anomaly thresholds are decisions, not magic.
- **[`infra/airflow/dags/daily_fintech_analytics.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/infra/airflow/dags/daily_fintech_analytics.py)** — the whole pipeline in about 70 lines. Note `depends_on_past` and the position of `dbt_test`.
- **[`infra/docker-compose.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/infra/docker-compose.yml)** — the full local stack.

Skim only, unless you specifically want to see the AI plumbing: **[`app/services/bi_engine.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/app/services/bi_engine.py)** (around 480 lines, the plan-validate-query-explain pipeline) and **[`reporting/inputs.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/inputs.py)** (around 580 lines, every quantitative input to the CFO report).

## Context, not my work

- **[`simulation/scenarios.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/simulation/scenarios.py)** — worth thirty seconds to see the six scenarios that give the data its shape. Not worth more.
- **[`infra/init-db/01_schema.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/infra/init-db/01_schema.sql)** — the raw schema, so you can see what staging is working from.

## How the project was run

- **[`model-implementation-planning/ROADMAP.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/ROADMAP.md)** — phase tracking, Gantt, and the deferred decisions. This is the scaffolding that kept an AI agent on task across sessions.
- **[`model-implementation-planning/IMPROVEMENTS.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/IMPROVEMENTS.md)** — eleven backlog items with effort and priority, including the gaps referenced elsewhere in these docs.
- **[`docs/learning-and-ownership.md`](learning-and-ownership.md)** — written before the code. What I own, what the agent built completely, and what I designed and reviewed.

## Skip these

- **`app/pages/1_Executive_Dashboard.py`** — around 500 lines of Plotly and mock-data helpers. Low signal unless charting is what you came for.
- **`model-implementation-planning/phase-*/README.md`** — agent briefs. Useful as evidence of how the work was scoped, not as reading.
- **`reporting/templates/cfo_report.html.j2`** — around 380 lines of styled HTML. Read [the rendered output](cfo_report_latest.html) instead.

## Deliberately not in the repository

Absences you might otherwise wonder about:

- **`.venv/`, `logs/`, `dbt/target/`, `dbt/dbt_packages/`, `__pycache__/`** — build output and dependencies.
- **`.env`** — holds the API key. `.env.example` documents every variable it needs.
- **`dbt/profiles.yml`** — machine-specific connection details; `dbt/profiles.example.yml` is the template.
- **`infra/airflow/config/airflow.cfg`** — 109 KB of generated Airflow defaults, recreated automatically on first start. It was tracked initially and removed; keeping generated config under version control makes every upgrade look like a change you made.
- **Two earlier CFO report drafts** — superseded by [the real generated report](cfo_report_latest.html), which is the only one worth looking at.
- **The original project brief, a `.docx`** — a binary GitHub cannot render. Everything in it that still matters is in these pages or in [ROADMAP.md](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/ROADMAP.md).
- **`app/components/`** — three small modules that no page ever imported. They were committed in the first push and then deleted; dead code in a repository is noise, and the history has it if it is ever wanted.
