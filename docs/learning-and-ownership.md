---
title: Learning and ownership plan
parent: Reference
nav_order: 3
eyebrow: Ownership
lede: This file was written before the code, not afterwards as a rationalisation. The roadmap tracks what gets built; this page tracks who owns it.
description: Ownership plan written before the code — what is mine, what an agent built, and how QA works.
has_toc: false
---

It sits next to [`model-implementation-planning/ROADMAP.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/ROADMAP.md): the roadmap tracks *what* gets built; this page tracks *who* owns it.

The point of using an agent was speed with a QA trail, not a black box that happens to run. I am training as an **analytics engineer**. The value I own is modelling, metric definitions and the trust layer. The UI is a demonstration surface for that work.

Every piece of work in this repository falls into one of three buckets.

| Bucket | Meaning |
|--------|---------|
| **Mine** | I designed it, wrote it or would sit in an interview and defend it line by line. |
| **Agent built completely** | The agent wrote the code. It stands in for work an analytics engineer would not do, or for application plumbing I specified but did not type. |
| **I designed and reviewed** | I made the product and design calls, the agent implemented them, and I verified the result with tests, traces and smoke checks. |

That split is how the agent made delivery **fast** without removing **QA**.

## Who owns which layer

| Layer | Represents | Bucket |
|-------|------------|--------|
| `simulation/` and Postgres `public` | Data engineering / source system — *bring data in* | Agent built completely |
| dbt staging → intermediate → marts | Analytics engineering | **Mine** |
| MetricFlow semantic layer | Metric definitions and trust | **Mine** |
| Airflow DAG | Orchestration | I designed and reviewed |
| Streamlit pages | Demonstration UI | I designed and reviewed |
| BI Assistant and CFO engine | Guardrailed AI on top of the warehouse | I designed and reviewed |

An analytics engineer does not create or move source data. The simulator is the upstream product team. My work starts at the raw tables.

## Mine

I own the warehouse contract: grain, business logic, tests and metric meaning.

- **dbt models.** Staging is thin. Intermediate facts are split by process (trading, funding, affiliates). Marts have a stated grain and `unique_combination_of_columns` tests. Serving models are shaped for one consumer.
- **Trading economics.** Client P&L vs broker position, instrument cost per lot, cashback, VIP treatment, affiliate cost netted to net revenue — in [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql) and the marts that consume it.
- **MetricFlow.** 57 metrics across three semantic models. I can walk `net_revenue` from raw to the metric, and I can explain why `withdrawal_ratio` is null when deposits are zero rather than a fake spike.
- **Limitations stated in business language.** Activity retention is not CRM churn. Per-client volume is not in the catalog. Those caveats are mine.

This is the part a data team would review first, and the part I would defend without opening a chat log.

## Agent built completely

- **`simulation/` and the raw schema.** By design. It is the data-engineering stand-in so the project can focus on transformation and trust.
- **Streamlit scaffolding** — page shells, layout, Plotly wiring, mock-data fallback.
- **Airflow boilerplate** — image, compose, DAG file structure.
- **Large application modules** once the design was fixed — `bi_engine.py`, `reporting/inputs.py`, the CFO HTML template.

I could not have typed those modules quickly from scratch. I also did not accept them unread. Speed came from the agent producing a working surface; quality came from specifying what had to be true before it wrote, and tracing output afterwards.

## I designed and reviewed

The agent implemented. I decided *what* it was allowed to implement, and I checked that the result matched.

**Orchestration.** Sequential backfill (`depends_on_past=True`, `catchup=True`) because the simulator has a user lifecycle. `dbt_test` as its own gate so a failing grain test stops the pipeline before the CFO report is generated.

**Dashboard.** Which KPIs, which comparisons, which SQL against serving marts — never against `public.*`. The agent turned that into pages.

**BI Assistant.** Guardrail design before code: allowlist from the semantic layer, plan validation, app-built filters, pandas for arithmetic, explainer that only sees returned numbers. Cheap questions stay on a fast model; anomaly and root-cause questions escalate. I had the pattern explained step by step, with a pause for my call at each one, *before* the agent wrote the engine.

**AI CFO.** Nine-section structure, what counts as an anomaly, which forecast method, deterministic inputs in Python, LLM for prose only. The agent scaffolded `reporting/` to that spec.

**Phase briefs, roadmap and backlog.** Constraints live in the repo so a stateless agent cannot reopen scope. Out-of-scope lists, deferred marts and [`IMPROVEMENTS.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/IMPROVEMENTS.md) are how I kept delivery fast without letting the agent invent a second project.

## How that made delivery fast, with QA

The agent removed the slow parts that are not analytics engineering: UI plumbing, simulator, DAG boilerplate, stitching modules together. I kept the slow parts that *are* the job: grain, metric meaning, what the AI is forbidden to do.

QA is not a pass at the end. It is how the agent was allowed to move quickly.

| Check | What it catches |
|-------|-----------------|
| Grain tests on every mart | A plausible join that fans out and overstates revenue |
| `dbt parse` and `mf query` before the app | A wrong metric that would otherwise look like an app bug |
| `dbt_test` as a DAG gate | A CFO report generated from a broken warehouse |
| Data Spot Check | Dashboard wrong vs mart wrong, in seconds |
| Fixed trace: app → serving → mart → intermediate → raw | Disagreement without a hunt through a 500-line module |
| Teach-then-build on the BI Assistant | Guardrails I can explain, so I can review the code that implements them |

If I cannot explain why a guardrail exists, I cannot review the code, and I have accepted a black box into my own project. The agent is a multiplier on that loop. It is not a substitute for it.
