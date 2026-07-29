# Learning & Ownership Plan

> Companion to `model-implementation-planning/ROADMAP.md`. The roadmap tracks *what* gets built;
> this file tracks *who* builds it and *why* — so the project stays a learning vehicle for
> analytics engineering, not just an AI-generated app.

## Guiding principle

I am training to be an **analytics engineer**. The value I own is the **data modeling, metric
definitions, and the trust layer** — not the UI. Streamlit is a *demonstration surface* for the
work behind the scenes, so the agent can carry most of that load.

**Mental model of the stack (and who owns what):**

| Layer | Role it represents | Owner |
|-------|--------------------|-------|
| `simulation/` | Data engineering / app devs — *bring data in* | Agent (I don't create or move source data as an AE) |
| Postgres `public` raw | Source system | Agent |
| dbt staging → intermediate → marts | **Analytics engineering** | **Me (deep)** |
| MetricFlow semantic layer | **Metric definitions / trust** | **Me (deep)** |
| Airflow DAG | Orchestration | Mostly agent, I understand concepts |
| Streamlit (dashboard / BI / CFO) | UI to *demonstrate* the work | Agent builds; I direct & own SQL/metric choices |

## Ownership matrix (per area)

| Area | I own (learn deeply) | Agent does for me |
|------|----------------------|-------------------|
| **Metric definition** | Review semantic + dbt layer myself; defend every metric | Nothing — this is mine. Agent only quizzes me (see interview Qs) |
| **Phase 4 visuals** | Decide *which* visuals; write the SQL behind each | Run Streamlit live, give visual guidelines, harmonize my SQL into the app |
| **BI Assistant** | Understand each step; make the design calls | Guide me step by step; explain the RAG/allowlist/guardrail pattern before coding |
| **AI CFO** | Decide report structure & sections; provide the business logic | Guide me, take my input, scaffold the engine once I've decided structure |
| **Phase 5 wrap-up** | Write the honest attribution narrative | Tally what was AI-generated vs. hand-built |

---

## Area 1 — Metric definition (my solo review, ~after Phase 4)

**Plan:** Once Phase 4 exists, I review the semantic layer (`dbt/models/semantic_models/metrics.yml`,
`semantic_*.yml`) and the dbt marts on my own, then test myself with the interview questions below.

**Agent's only job here:** ask me these questions, not answer them.

### Interview question bank (metric / semantic / dbt layer)

**Modeling & grain**
1. What is the grain of `mrt_company_daily_kpi` vs `mrt_daily_user_activity`? How do you prove a model is at the grain you claim?
2. Why split `int_fct_daily_trading`, `int_fct_daily_funding`, `int_fct_affiliates_cost` instead of one wide fact?
3. Where does business logic belong — staging, intermediate, or mart — and why?
4. How do `mrt_user_lifetime` and `mrt_user_retention` differ in grain and use case?

**Metric definitions & semantic layer**
5. Walk through `net_revenue` from raw `public` tables to the MetricFlow metric. Where is it actually computed?
6. Why compute KPIs in the warehouse and let the LLM only interpret them? What breaks if you don't?
7. Difference between a metric defined as a dbt mart column vs. a MetricFlow metric? When do you need both?
8. How do you define `withdrawal_ratio` so it's not misleading on low-volume days?
9. What's the difference between `net_revenue_vs_target` and `net_revenue_attainment`?

**Trust, tests & limitations**
10. Which dbt tests guard grain/uniqueness, and what would a failure mean upstream?
11. Why is retention here "activity-based" and not true CRM churn? How would you caveat that to a stakeholder?
12. A KPI looks wrong on the dashboard — trace your debugging path from Streamlit back to raw.

**Orchestration awareness**
13. Why `depends_on_past=True` and `catchup=True` for `daily_fintech_analytics`? What problem does sequential backfill solve?
14. Why is `dbt test` its own gate task after `dbt run`?

---

## Area 2 — Phase 4 visuals (I drive, agent harmonizes)

**Working agreement**
- Agent runs Streamlit live so I see changes immediately.
- Agent gives **visual guidelines** (chart type per metric, layout, UX) — I make the final call.
- **I write the SQL** for each visual against `analytics_dev` marts; agent wires it into the app cleanly.
- Data rule (from Phase 4 README): query marts / MetricFlow only — never raw `public.*` from the app.

**Dashboard v1 target (my SQL, agent's plumbing):** KPI cards (net revenue, gross revenue, active
users, gross deposits, net flow, withdrawal ratio) + revenue trend, deposits vs withdrawals,
active users, regional table.

---

## Area 3 — BI Assistant (agent guides me step by step)

I want to *learn the pattern*, so agent teaches before building. Expected steps:
1. Intent → metric retrieval (allowlisted names only)
2. RAG over `metrics.yml` + `marts.yml` chunks
3. Compiled/allowed SQL → real numbers
4. LLM explains numbers (never invents them)
5. Guardrails: prompt size cap, token logging, no hallucinated values

Agent pauses at each step for my decisions; I should be able to explain why each guardrail exists.

---

## Area 4 — AI CFO (agent guides, I decide structure)

Agent gets my input on the 9-section report template and what each section needs, then scaffolds
`cfo_engine.py`. Inputs are precomputed in Python (snapshots, deltas, targets, anomalies, forecasts);
LLM only writes prose. I decide: which sections matter, what counts as an anomaly, forecast method.

---

## Area 5 — Phase 5 attribution (honesty about AI vs. me)

When wrapping up, document the split openly:

| Built fully by AI | Built / owned by me |
|-------------------|---------------------|
| `simulation/` (represents data-eng / app devs bringing data in) | dbt marts & metric definitions |
| Streamlit UI scaffolding & components | Visual choices + the SQL behind them |
| Airflow boilerplate | Orchestration design decisions |
| BI/CFO code plumbing | Metric trust model, report structure, business logic |

Framing for the portfolio README: *"As the analytics engineer, I don't create or move source data
— that's the simulation standing in for data engineering. My work is everything from raw tables to
trusted metrics, and the guardrails that let AI safely interpret them."*
