---
title: Skills
nav_order: 7
---

# Skills

Framed for an **analytics engineer** role. Everything below points at something in this repository that you can open and check.

## Technical

**Dimensional modelling and grain discipline.** Twenty-one models in four layers, with facts split by business process rather than by output. Every mart states its grain and has a test enforcing it. Grain is the thing I am most careful about, because a fan-out is the most common way a number silently doubles.

**SQL.** The intermediate layer is where the real work is: CTE-structured trading economics with per-instrument cost and cashback rates, a VIP uplift that varies by instrument group, and acquisition cost netted off at the mart layer. See [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql).

**dbt Core.** Sources, seeds, staging through serving, `dbt_utils`, 83 tests, model documentation, exposures declaring downstream consumers, and a deliberate materialization strategy — views where transformation is thin, tables where things get read repeatedly.

**Semantic layer with MetricFlow.** 57 metrics across simple, ratio, cumulative and derived types, on three semantic models, with a time spine supporting month-to-date and rolling-window metrics. The [semantic layer page](03-semantic-layer-and-metric-trust.md) explains the judgement calls rather than just the count.

**Orchestration with Airflow 3.** A daily DAG with sequential backfill semantics chosen because the source data has a stateful user lifecycle, and testing as a gate task upstream of anything that publishes numbers.

**Postgres and Docker.** The whole stack runs from one compose file: warehouse, Airflow metadata database, scheduler, API server and DAG processor, on a custom image carrying dbt and MetricFlow.

**AI application guardrails.** Allowlist generated from the semantic layer, plan validation before execution, app-constructed filters with an operator whitelist, deterministic computation in pandas, and an explainer that only sees returned numbers. Detailed in [BI implementation strategy](04-bi-implementation-strategy.md).

**Python, at a working level.** pandas for analysis, Jinja templating, subprocess integration, module organisation. Honest scope on this below.

## Soft

**Scoping and sequencing.** Five phases with explicit deliverables, weighted progress tracking, and a brief per phase that states what is out of scope as clearly as what is in it.

**Deciding what not to build.** The affiliate summary mart, the regional daily KPI mart, a FastAPI service tier and an in-app pipeline health page were all considered and dropped, each with the reason recorded. Phase 5 stopped at documentation rather than chasing a hosted demo. Knowing when a thing is finished is a skill.

**Communicating to different audiences.** This site is written for two: someone hiring, and someone who runs an analytics function. The same project, described at different resolutions.

**Honest attribution.** The [ownership page](05-ownership-and-cursor-workflow.md) states plainly which parts an AI agent wrote. It would have been easy to omit and would have collapsed the first time someone asked me to walk through `bi_engine.py`.

**Stakeholder framing of limitations.** Retention here is activity-based, not churn, and it is labelled that way everywhere it appears. A caveat volunteered up front is credibility; the same caveat discovered later is a problem.

**Cost awareness.** The AI layer was built to roughly 20 euro per month, with model tiering, a local path for questions that need no model at all, and token counts surfaced in the interface.

## Where I am weak, and what I do about it

Stated deliberately. Every one of these is real.

**Front-end work.** Streamlit and Plotly are not my strength, and the app code shows it — one dashboard page runs to about 590 lines with chart helpers and mock-data generators inline, where a tidier build would have factored them out. *What I do about it:* I own which visual answers which question and the SQL behind it, and I built the Data Spot Check page so that app-layer bugs can never be mistaken for warehouse bugs.

**Authoring large Python systems.** I specified and reviewed `bi_engine.py` and `reporting/inputs.py`; I did not write them from scratch and could not have done so at that speed. *What I do about it:* the parts where correctness is load-bearing are small, isolated and readable — `forecasting.py` and `anomalies.py` are around 120 lines each of pure functions — and the architecture keeps computation in Python and language out of it, so the complex modules are wiring rather than logic I cannot verify.

**No Python test suite and no CI.** There is no pytest anywhere in this project and no GitHub Actions workflow. This is the clearest gap. *What I do about it today:* 83 dbt tests run as a gating task in the pipeline, so the data is covered even though the application code is not. *What I would do next:* pytest over `forecasting.py` and `anomalies.py` first, since they are pure functions with obvious edge cases, then `dbt build` on pull requests.

**Cloud warehouse scale.** This is Postgres on a laptop. There are no incremental models, because the dataset rebuilds in full in seconds and adding incrementality would have been complexity without a reason. The dbt and modelling skills transfer directly to Snowflake or BigQuery; the cost and performance tuning instincts that come from operating at that scale are not something I can claim from this project.

**Production data engineering.** Ingestion, change data capture and streaming are not demonstrated here, and the simulator explicitly stands in for them. That was a scoping decision about what an analytics engineer owns, not an attempt to cover a gap.
