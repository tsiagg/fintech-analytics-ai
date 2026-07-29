# Fintech Analytics AI

Analytics engineering portfolio: dbt marts, a MetricFlow semantic layer, Airflow orchestration, and a guardrailed AI BI layer on a simulated fintech warehouse.

**[Read the full documentation site](https://tsiagg.github.io/fintech-analytics-ai/)**

<!-- Hero screenshot slot: uncomment once the file exists. See docs/assets/screenshots/CAPTURE-GUIDE.md
![Executive dashboard](docs/assets/screenshots/executive-dashboard.png)
-->

---

## What this is

A complete analytics stack for a fictional retail trading broker, built end to end so that the analytics engineering work has somewhere real to live. A simulator generates daily trades, deposits, withdrawals and signups into Postgres. dbt turns that into tested marts and a semantic layer of 57 governed metrics. Airflow runs the whole thing daily. Streamlit exposes it through a dashboard, a chat-based BI assistant, and an automatically generated CFO report.

The point of the project is not the app. It is the layer underneath: **defining metrics once, testing them, and making them the only thing an LLM is allowed to talk about.**

## Architecture

```mermaid
flowchart LR
    Sim["simulation/<br/>scenario engine"] --> Raw["Postgres raw<br/>users, trades, deposits, withdrawals"]
    Raw --> Staging["dbt staging<br/>8 views"]
    Staging --> Intermediate["dbt intermediate<br/>5 facts and dims"]
    Intermediate --> Marts["dbt marts<br/>5 core + 2 serving tables"]
    Marts --> Semantic["MetricFlow<br/>3 semantic models, 57 metrics"]
    Marts --> Dashboard["Streamlit dashboard"]
    Semantic --> BI["BI Assistant"]
    Semantic --> CFO["AI CFO report"]
    Airflow["Airflow DAG<br/>daily_fintech_analytics"] -.orchestrates.-> Sim
    Airflow -.-> Marts
    Airflow -.-> CFO
```

## The trust model

Every number is computed in the warehouse. The LLM never writes SQL and never sees the database. It receives a validated result set and is asked to explain it. A question is turned into a plan of allowlisted metric and dimension names, the plan is validated against the semantic catalog before anything runs, and MetricFlow executes it. If a metric is not defined in YAML, it cannot be asked for.

## Stack

Postgres 16, dbt Core with `dbt_utils`, MetricFlow, Airflow 3.1.5 on LocalExecutor, Streamlit with Plotly, OpenRouter for the LLM layer, all running locally under Docker Compose.

## Ownership, honestly

I own the analytics engineering: the dimensional models, the grain decisions, the metric definitions, the tests, and the guardrail design that constrains the AI. The data simulator stands in for a data engineering team, and the Streamlit and Python application code was largely AI-generated to my direction and review.

That split is documented in detail, including where my technical depth runs out and what I do to compensate, in [Ownership and Cursor workflow](https://tsiagg.github.io/fintech-analytics-ai/05-ownership-and-cursor-workflow.html) and [Skills](https://tsiagg.github.io/fintech-analytics-ai/06-skills.html).

## A 60-second tour

If you only open five files, open these:

- [`dbt/models/marts/mrt_daily_user_activity.sql`](dbt/models/marts/mrt_daily_user_activity.sql) — the core mart, at user x day grain
- [`dbt/models/semantic_models/metrics.yml`](dbt/models/semantic_models/metrics.yml) — 57 metrics: simple, ratio, cumulative and derived
- [`dbt/models/marts/marts.yml`](dbt/models/marts/marts.yml) — the documentation and grain tests that make the marts trustworthy
- [`app/services/metrics.py`](app/services/metrics.py) — the validation gate every AI-planned query has to pass
- [`infra/airflow/dags/daily_fintech_analytics.py`](infra/airflow/dags/daily_fintech_analytics.py) — the daily pipeline

A guided tour of the rest, including what to skip, is in the [file guide](https://tsiagg.github.io/fintech-analytics-ai/07-file-guide.html).

## Status

Phases 1 to 4 are complete: raw simulation, dbt core and semantic layers, Airflow orchestration, and all four Streamlit surfaces. Phase 5 was scoped as portfolio packaging and deliberately stopped at documentation rather than adding a hosted demo. Progress is tracked in [ROADMAP.md](model-implementation-planning/ROADMAP.md) and open ideas in [IMPROVEMENTS.md](model-implementation-planning/IMPROVEMENTS.md).

## Running it

`docker compose -f infra/docker-compose.yml up -d` brings up Postgres and Airflow. The dashboard runs without an LLM key; only the BI Assistant and CFO report need one. Full steps are in [Run it yourself](https://tsiagg.github.io/fintech-analytics-ai/08-run-it-yourself.html) and the operational detail in [docs/runbook.md](docs/runbook.md).
