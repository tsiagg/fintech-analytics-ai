---
title: What I built
parent: Work
nav_order: 1
---

# What I built

Four user-facing surfaces sitting on one tested warehouse, refreshed by one daily pipeline. Each surface exists to demonstrate a different thing.

## The daily pipeline

<p><span class="case-k">Problem</span> If tests are optional, a bad grain join can still reach an executive report.</p>
<p><span class="case-k">Approach</span> One daily Airflow DAG, sequential backfill, and <code>dbt_test</code> as its own gate before anything is published.</p>
<p><span class="case-k">What I built</span> <code>daily_fintech_analytics</code>: <code>run_simulation</code> → <code>dbt_run</code> → <code>dbt_test</code> → <code>generate_cfo_report</code>.</p>
<p><span class="case-k">Why it matters</span> A failing grain test stops the pipeline before the CFO report is generated from bad numbers.</p>
<p class="case-tech">Airflow · dbt Core · Postgres</p>

One Airflow DAG, [`daily_fintech_analytics`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/infra/airflow/dags/daily_fintech_analytics.py), runs four tasks in sequence:

`run_simulation` generates one day of source data, `dbt_run` rebuilds the models, `dbt_test` gates the result, and `generate_cfo_report` writes an executive report for that date.

![Airflow run of daily_fintech_analytics: all four tasks succeeding, with the recent-run grid on the left](assets/screenshots/airflow-dag.png)

Two configuration choices matter more than the task list. `depends_on_past=True` with `catchup=True` means a gap in history backfills strictly one day at a time and in order, which is required because the simulator's user lifecycle depends on prior days. And `dbt_test` is its own task rather than a flag on the run, so a failing grain test stops the pipeline **before** the CFO report is generated from bad numbers.

## Executive dashboard

<p><span class="case-k">Problem</span> An executive does not need every column. They need a few comparisons that answer whether activity, revenue and funding are on plan.</p>
<p><span class="case-k">Approach</span> Shape serving marts for known queries. Pick KPIs and period comparisons that support a decision, not a gallery of charts.</p>
<p><span class="case-k">What I built</span> Four KPI cards with sparklines, month-to-date and week-over-week badges, a weekly revenue breakdown that toggles between region and country, and per-user trend lines.</p>
<p><span class="case-k">Why it matters</span> The marts are fit for consumption, and things can be left off the screen.</p>
<p class="case-tech">Python · SQL · Streamlit</p>

![Executive dashboard: KPI cards with sparklines and weekly revenue by region](assets/screenshots/executive-dashboard.png)

It reads the serving marts directly rather than going through the semantic layer, because a dashboard has fixed, known queries and does not need runtime metric resolution. It falls back to mock data when Postgres is unavailable so the app still demos on a laptop with nothing running.

## BI Assistant

<p><span class="case-k">Problem</span> Ad-hoc questions about warehouse numbers are useful. Letting a model write SQL against raw tables produces confident, plausible, wrong answers.</p>
<p><span class="case-k">Approach</span> The question becomes a plan naming metrics and dimensions from an allowlist. The plan is validated, MetricFlow executes it, pandas does period-over-period and anomaly arithmetic, and only then does an LLM see the numbers.</p>
<p><span class="case-k">What I built</span> A chat surface that returns a chart, a table and an explanation. Cheap questions stay on a fast model; anomaly and root-cause questions escalate. Neither model writes SQL.</p>
<p><span class="case-k">Why it matters</span> Guardrails and cost routing without letting either model invent a business number.</p>
<p class="case-tech">MetricFlow · Python · pandas</p>

![BI Assistant: regional anomaly and root-cause question, with a chart, outlier table and the model badge](assets/screenshots/bi-assistant-2.png)

The full chain is described in [BI implementation strategy](04-bi-implementation-strategy.md).

A straightforward descriptive question stays on the cheap model. The badge under the answer shows `deepseek-v4-flash` and the token count.

![BI Assistant: revenue by region over two weeks, answered on the cheap flash model with the model and token badge visible](assets/screenshots/bi-assistant-1.png)

Ask about anomalies or root cause and the router escalates to the stronger model — that is the screenshot at the top of this section. Same MetricFlow numbers, same chart and table; only the explainer tier changes. The badge there shows `deepseek-v4-pro`.

## AI CFO report

<p><span class="case-k">Problem</span> Leadership still needs a structured view of what happened when nobody typed a question.</p>
<p><span class="case-k">Approach</span> A fixed nine-section report, generated on a schedule. Every quantitative element is computed in Python before the LLM is involved.</p>
<p><span class="case-k">What I built</span> An Airflow task that writes the HTML report to Postgres, and a Streamlit page that renders the latest one.</p>
<p><span class="case-k">Why it matters</span> A report worth reading needs deterministic inputs and a template, not a one-shot prompt.</p>
<p class="case-tech">Airflow · Python · Jinja2</p>

The nine sections are: executive summary, trends against target, revenue, user activity, cash flow, regional performance, risks, forecast, and recommended actions.

Month-end projections come from a linear regression with a run-rate fallback ([`reporting/forecasting.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/forecasting.py)), anomalies from z-scores plus explicit business rules ([`reporting/anomalies.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/anomalies.py)). The model writes the prose around those facts and nothing else.

[Open a real generated report](cfo_report_latest.html).

## Data spot check

<p><span class="case-k">Problem</span> When a dashboard number looks wrong, the first question is whether the mart is wrong or the dashboard is.</p>
<p><span class="case-k">Approach</span> A dedicated page that dumps the marts with a date filter and a CSV export.</p>
<p><span class="case-k">What I built</span> Data Spot Check — the least glamorous page and the one I use most.</p>
<p><span class="case-k">Why it matters</span> Reconciliation in about ten seconds, after every change, instead of trusting the pretty surface.</p>
<p class="case-tech">Streamlit · SQL</p>
