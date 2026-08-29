---
title: Profile
parent: About
nav_order: 1
permalink: /06-skills.html
redirect_from:
  - /cv/
---

# Skills

This project demonstrates how I approach an **analytics engineering** role: understand the business model, turn it into reliable data products, and communicate the result in a form that supports decisions. Every capability below is tied to evidence in this repository.

## Recruiter summary

- **Analytics engineering:** SQL, dbt Core, dimensional modelling, data quality, MetricFlow and semantic-layer design
- **Business analytics:** brokerage unit economics, customer acquisition, retention, cash flow, target setting and performance management
- **Data products:** executive dashboards, governed self-service BI and scheduled management reporting
- **Delivery:** Airflow orchestration, Postgres, Docker, requirements scoping and iterative delivery
- **AI-enabled analytics:** constrained LLM workflows in which governed data is computed first and AI is used only for interpretation
- **Ways of working:** stakeholder communication, transparent ownership, quality assurance and practical prioritisation

## Business and domain knowledge

### Retail brokerage economics

I modelled how a retail trading broker earns and spends money at transaction level. The revenue logic separates the client's profit and loss from the broker's position, applies instrument-specific trading cost per lot, deducts cashback, and adjusts incentives for VIP clients. Affiliate acquisition cost is then deducted to produce net trade revenue.

This demonstrates that I can translate commercial rules into auditable data logic rather than treating revenue as an unexplained source-system field. The implementation is visible in [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql) and [`mrt_daily_user_activity.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/mrt_daily_user_activity.sql).

### Customer acquisition and lifecycle analysis

The model connects acquisition channel and affiliate cost to user activity and revenue, making it possible to evaluate growth by both volume and commercial value. Cohort models measure time to first trade and return-to-activity at day 0, 1, 7 and 30.

I distinguish **activity retention** from churn: the available data can show whether a client returned, but not whether an account was formally closed. That distinction matters because a technically valid metric can still mislead a stakeholder if its business meaning is overstated.

### Client funding and cash-flow monitoring

Gross deposits, withdrawals and net flow are modelled separately because they answer different management questions. The withdrawal ratio is calculated as withdrawals divided by deposits, with a null result when deposits are zero. This avoids presenting an undefined ratio as either zero or an artificial spike.

These measures support monitoring of funding momentum, unusual outflows and the relationship between client activity and deposited funds. They are analytical indicators in this simulated project, not a claim to have implemented treasury, safeguarding or regulatory reporting.

### Commercial performance management

Monthly active users, net revenue and gross deposits are compared with regional targets in both absolute and percentage terms. I use:

- **variance** to size the gap to plan;
- **attainment** to compare regions of different sizes fairly;
- **month-to-date and rolling measures** to track direction before month end; and
- **forecast and anomaly outputs** to focus an executive report on exceptions and actions.

This reflects the questions a finance or commercial leader asks: Are we on plan? Where is the gap? Is it caused by customer activity, revenue yield or funding behaviour? Which region requires attention?

### Product and instrument performance

Instrument-level models track trade count, active traders, volume, company P&L, trading cost, cashback and revenue by symbol and region. Ratio metrics such as revenue per trade, trades per trader and cashback as a share of revenue make performance comparable across instruments with different levels of activity.

### Metric governance and decision support

I treat a metric as a business contract, not just a calculation. Each important KPI has a definition, grain, valid dimensions and known limitations. The dashboard, BI Assistant and CFO report resolve back to the same modelled logic, reducing the risk that teams make decisions from conflicting versions of "net revenue" or "active user".

## Technical capabilities

### Analytics engineering

**Dimensional modelling and grain discipline.** Twenty-one dbt models are organised into staging, intermediate, mart and serving layers. Facts are split by business process, and every mart has a stated and tested grain. This prevents duplicate-producing joins from silently overstating commercial results.

**SQL.** The intermediate layer is where the real work is: CTE-structured trading economics with per-instrument cost and cashback rates, a VIP uplift that varies by instrument group, and acquisition cost netted off at the mart layer. See [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql).

**dbt Core.** Sources, seeds, staging through serving, `dbt_utils`, 83 tests, model documentation, exposures declaring downstream consumers, and a deliberate materialization strategy — views where transformation is thin, tables where things get read repeatedly.

**Semantic layer with MetricFlow.** 57 metrics across simple, ratio, cumulative and derived types, on three semantic models, with a time spine supporting month-to-date and rolling-window metrics. The [semantic layer page](03-semantic-layer-and-metric-trust.md) explains the judgement calls rather than just the count.

### Data platform and delivery

**Orchestration with Airflow 3.** A daily DAG with sequential backfill semantics chosen because the source data has a stateful user lifecycle, and testing as a gate task upstream of anything that publishes numbers.

**Postgres and Docker.** The whole stack runs from one compose file: warehouse, Airflow metadata database, scheduler, API server and DAG processor, on a custom image carrying dbt and MetricFlow.

**Python.** pandas for deterministic analysis, Jinja for report generation, subprocess integration with MetricFlow, and modular reporting components for forecasting and anomaly detection. I am comfortable reading, testing and adapting Python analytics code; larger application modules were built collaboratively with an AI coding agent.

### Trusted AI and business intelligence

**AI application guardrails.** Allowlist generated from the semantic layer, plan validation before execution, app-constructed filters with an operator whitelist, deterministic computation in pandas, and an explainer that only sees returned numbers. Detailed in [BI implementation strategy](04-bi-implementation-strategy.md).

**Executive information design.** KPI scorecards, period comparisons, regional and instrument breakdowns, anomaly flags and a structured nine-section CFO report. I selected outputs based on the decision they support, not on how many visualisations could fit on a page.

**Reconciliation and observability.** A dedicated Data Spot Check surface separates warehouse issues from presentation issues, while dbt tests gate publication. This creates a clear investigation path from app to serving mart, core mart, intermediate model and source.

## Professional and collaboration skills

**Requirements translation.** I converted business concepts such as revenue, client activity, target attainment and funding pressure into explicit definitions, grains, dimensions and tests. This is the bridge between stakeholder language and maintainable data products.

**Scoping and sequencing.** The project was delivered in five phases with explicit outcomes, dependencies and out-of-scope boundaries. Ideas that did not support the current objective were recorded in a prioritised backlog rather than allowed to disrupt delivery.

**Stakeholder communication.** The same work is communicated at different levels: concise portfolio summaries for recruiters, model-level detail for analytics engineers, and exception-focused reporting for executives. Limitations are stated in business language so users know what decisions a metric can and cannot support.

**Quality ownership.** I use grain tests, semantic-layer smoke tests, source-to-dashboard reconciliation and explicit publication gates. When a result looks wrong, I follow a defined trace through the data layers instead of adjusting the presentation until it looks plausible.

**Risk and control awareness.** I designed the AI layer so it cannot create SQL, invent a metric or bypass the approved semantic catalog. The design favours traceability and refusal over a confident answer that cannot be verified.

**Cost awareness.** The AI layer was built to roughly 20 euro per month, with model tiering, a local path for questions that need no model at all, and token counts surfaced in the interface.

**Transparent collaboration with AI.** I document where an AI agent contributed code, what I specified, and how I verified the result. The [ownership page](05-ownership-and-cursor-workflow.md) explains this working model in detail.

## Current boundaries and development priorities

The project is intentionally strongest in analytics engineering. The following boundaries keep the claims above accurate and identify sensible next steps.

- **Application engineering:** Streamlit and Plotly are supporting presentation tools here, not my primary specialism. I own the analytical question, visual choice and underlying data; a future refactor would separate chart helpers and mock-data generation from page code.
- **Python engineering:** I can work effectively with analytics-focused Python and review larger modules, but I do not claim the same depth as in SQL and dbt. The most important deterministic logic is isolated in small forecasting and anomaly modules that are easier to test and verify.
- **Automated delivery:** dbt provides 83 data tests, but the repository does not yet have pytest coverage or a CI workflow. The next priorities are unit tests for forecasting and anomaly edge cases, followed by `dbt build` on pull requests.
- **Cloud scale:** this project runs on local Postgres and rebuilds quickly, so incremental modelling and warehouse cost optimisation are not demonstrated. Those would need to be validated in a Snowflake, BigQuery or similar production environment.
- **Upstream data engineering:** ingestion, change data capture and streaming are outside scope. The simulator represents upstream product systems so the project can focus on transformation, governance and decision support.

## Best evidence to review

1. [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql) — brokerage revenue logic
2. [`marts.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/marts.yml) — model contracts, documentation and grain tests
3. [`metrics.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/semantic_models/metrics.yml) — governed business metrics
4. [`app/services/metrics.py`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/app/services/metrics.py) — validation gate for AI-planned queries
5. [Generated CFO report](cfo_report_latest.html) — the executive-facing output
