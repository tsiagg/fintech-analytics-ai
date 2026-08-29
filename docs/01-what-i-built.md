---
title: What I built
parent: Work
nav_order: 1
eyebrow: Analytics engineering
lede: Four user-facing surfaces sitting on one tested warehouse, refreshed by one daily pipeline. Each surface exists to demonstrate a different thing.
tech: SQL · dbt · Python · Airflow · Streamlit
description: Four surfaces on one tested warehouse — executive dashboard, BI Assistant, AI CFO report, and data spot check.
has_toc: false
---

<section class="case-block" markdown="1" id="context">
<p class="eyebrow">01 — Context</p>
<h2>What problem this addresses</h2>

<p>A warehouse that is tested but never consumed is incomplete. A dashboard or chat interface that invents its own figures is worse. This project needed both: numbers that can be audited, and surfaces a person can actually use to decide.</p>

<p>The commercial setting is a simulated retail trading broker. Source data is synthetic. The work to judge is the pipeline, the models, and the four products that read from them.</p>
</section>

<section class="case-block" markdown="1" id="approach">
<p class="eyebrow">02 — Approach</p>
<h2>How the problem was approached</h2>

<p>If tests are optional, a bad grain join can still reach an executive report. The daily pipeline treats testing as a gate, not a flag.</p>

<p>One Airflow DAG, <a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/infra/airflow/dags/daily_fintech_analytics.py"><code>daily_fintech_analytics</code></a>, runs four tasks in sequence: <code>run_simulation</code> generates one day of source data, <code>dbt_run</code> rebuilds the models, <code>dbt_test</code> gates the result, and <code>generate_cfo_report</code> writes an executive report for that date.</p>

<p>Two configuration choices matter more than the task list. <code>depends_on_past=True</code> with <code>catchup=True</code> means a gap in history backfills strictly one day at a time and in order, which is required because the simulator's user lifecycle depends on prior days. And <code>dbt_test</code> is its own task rather than a flag on the run, so a failing grain test stops the pipeline <strong>before</strong> the CFO report is generated from bad numbers.</p>

<p class="tech-meta">Airflow · dbt Core · Postgres</p>
</section>

<section class="case-block" markdown="1" id="architecture">
<p class="eyebrow">03 — Architecture</p>
<h2>How the system works</h2>

<p>The four surfaces sit on the same warehouse and use different query paths on purpose. The executive dashboard reads serving marts directly, because its queries are fixed and known. The BI Assistant resolves metrics at runtime through MetricFlow. The CFO report is an Airflow task that runs only after tests pass. Data Spot Check dumps the marts so a wrong number can be traced.</p>

<p>Layers, grain and materialization are written up in <a href="{{ '/02-architecture-and-data-model.html' | relative_url }}">Architecture and data model</a>. How AI is constrained is in <a href="{{ '/04-bi-implementation-strategy.html' | relative_url }}">BI implementation strategy</a>.</p>

<figure class="figure">
  <img
    src="{{ '/assets/screenshots/airflow-dag.png' | relative_url }}"
    alt="Airflow run of daily_fintech_analytics: all four tasks succeeding, with the recent-run grid on the left."
    width="1600"
    height="900"
    loading="lazy"
    decoding="async">
  <figcaption>A green run of daily_fintech_analytics: simulation, dbt run, dbt test, then the CFO report.</figcaption>
</figure>
</section>

<section class="case-block" markdown="1" id="implementation">
<p class="eyebrow">04 — Implementation</p>
<h2>What was actually built</h2>

<h3 id="executive-dashboard">Executive dashboard</h3>

<p>Four KPI cards with sparklines, month-to-date and week-over-week badges, a weekly revenue breakdown that toggles between region and country, and per-user trend lines. KPIs and period comparisons were chosen to support a decision, not to fill a gallery of charts.</p>

<p class="tech-meta">Python · SQL · Streamlit</p>

<figure class="figure">
  <img
    src="{{ '/assets/screenshots/executive-dashboard.png' | relative_url }}"
    alt="Executive dashboard: KPI cards with sparklines and weekly revenue by region."
    width="1600"
    height="900"
    loading="lazy"
    decoding="async">
  <figcaption>Executive dashboard — net revenue, active users, net flow and withdrawal ratio, with weekly revenue by region.</figcaption>
</figure>

<p>It reads the serving marts directly rather than going through the semantic layer, because a dashboard has fixed, known queries and does not need runtime metric resolution. It falls back to mock data when Postgres is unavailable so the app still demos on a laptop with nothing running.</p>

<h3 id="bi-assistant">BI Assistant</h3>

<p>Ad-hoc questions about warehouse numbers are useful. Letting a model write SQL against raw tables produces confident, plausible, wrong answers. Here the question becomes a plan naming metrics and dimensions from an allowlist. The plan is validated, MetricFlow executes it, pandas does period-over-period and anomaly arithmetic, and only then does an LLM see the numbers.</p>

<p>The chat surface returns a chart, a table and an explanation. Cheap questions stay on a fast model; anomaly and root-cause questions escalate. Neither model writes SQL.</p>

<p class="tech-meta">MetricFlow · Python · pandas</p>

<figure class="figure">
  <img
    src="{{ '/assets/screenshots/bi-assistant-2.png' | relative_url }}"
    alt="BI Assistant: regional anomaly and root-cause question, with a chart, outlier table and the model badge."
    width="1600"
    height="900"
    loading="lazy"
    decoding="async">
  <figcaption>Anomaly and root-cause question, escalated to the stronger model. Numbers still come from MetricFlow and pandas.</figcaption>
</figure>

<p>The full chain is described in <a href="{{ '/04-bi-implementation-strategy.html' | relative_url }}">BI implementation strategy</a>.</p>

<p>A straightforward descriptive question stays on the cheap model. The badge under the answer shows <code>deepseek-v4-flash</code> and the token count.</p>

<figure class="figure">
  <img
    src="{{ '/assets/screenshots/bi-assistant-1.png' | relative_url }}"
    alt="BI Assistant: revenue by region over two weeks, answered on the cheap flash model with the model and token badge visible."
    width="1600"
    height="900"
    loading="lazy"
    decoding="async">
  <figcaption>Descriptive question — revenue by region over two weeks — answered on the flash model, with model and token count visible.</figcaption>
</figure>

<h3 id="ai-cfo-report">AI CFO report</h3>

<p>Leadership still needs a structured view of what happened when nobody typed a question. A fixed nine-section report is generated on a schedule. Every quantitative element is computed in Python before the LLM is involved.</p>

<p>An Airflow task writes the HTML report to Postgres, and a Streamlit page renders the latest one. The nine sections are: executive summary, trends against target, revenue, user activity, cash flow, regional performance, risks, forecast, and recommended actions.</p>

<p>Month-end projections come from a linear regression with a run-rate fallback (<a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/forecasting.py"><code>reporting/forecasting.py</code></a>), anomalies from z-scores plus explicit business rules (<a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/reporting/anomalies.py"><code>reporting/anomalies.py</code></a>). The model writes the prose around those facts and nothing else.</p>

<p class="tech-meta">Airflow · Python · Jinja2</p>

<p><a class="text-link" href="{{ '/cfo_report_latest.html' | relative_url }}">Open a real generated report →</a></p>

<h3 id="data-spot-check">Data spot check</h3>

<p>When a dashboard number looks wrong, the first question is whether the mart is wrong or the dashboard is. A dedicated page dumps the marts with a date filter and a CSV export. It is the least glamorous page and the one I use most — reconciliation in about ten seconds, after every change, instead of trusting the pretty surface.</p>

<p class="tech-meta">Streamlit · SQL</p>
</section>

<section class="case-block" markdown="1" id="results">
<p class="eyebrow">05 — Results / Evidence</p>
<h2>What can be demonstrated</h2>

<p>The screenshots above are from the running stack, not mockups. The warehouse behind them is the same one described in the architecture and semantic-layer pages.</p>

{% include metrics.html %}

<p>A failing grain test stops the pipeline before the CFO report is generated. The Airflow screenshot in Architecture is a completed run of that sequence.</p>
</section>

<section class="case-block" markdown="1" id="reflection">
<p class="eyebrow">06 — Reflection</p>
<h2>What I would keep, and what I would change</h2>

<p>The dashboard does not go through MetricFlow. That is a deliberate choice for fixed queries, and it is also a gap: the BI tool and the assistant share definitions only because both resolve back to the same intermediate models, not because they share a query API. On a real team I would want the semantic layer to be the interface the BI tool uses too.</p>

<p>Leaving charts off the executive page was as important as putting the four KPIs on it. Data Spot Check exists because I do not trust a surface I cannot reconcile.</p>

<p>Known inefficiencies in the assistant — an eager retry, and a catalog that is not trimmed by relevance — are logged in the backlog rather than hidden. They are described in <a href="{{ '/04-bi-implementation-strategy.html' | relative_url }}">BI implementation strategy</a>.</p>
</section>

<section class="case-block" markdown="1" id="transparency">
<p class="eyebrow">07 — Transparency</p>
<h2>What I built, and what an agent built</h2>

<p>I chose which visuals answer which question and wrote the SQL behind the dashboard. An AI coding agent turned that into working Streamlit pages. Airflow boilerplate is agent-written; sequential backfill and <code>dbt_test</code> as a separate gate were my design calls. The CFO HTML template is agent-written; the nine-section structure and the rule that every quantitative element is computed first are mine.</p>

<p>The dbt models, tests and metric YAML are mine. The full split is on <a href="{{ '/05-ownership-and-cursor-workflow.html' | relative_url }}">How this project was built</a>.</p>
</section>
