# Phase 2 — Analytics engineering (dbt + KPI modeling)

**Parent brief:** See `../Analytics Project Summary - Fintech Simulation.docx`.

## Goal

Transform **raw** transactional data from Phase 1 into **business KPIs** and a **semantic analytics layer** using **dbt**.

**Prerequisite:** Phase 1 raw data in Postgres. Load or extend history manually while building models (`python -m simulation --date …` in `docs/runbook.md`). **Airflow is not required in this phase** — automation lands in Phase 3 once marts and tests are stable.

**Phase 4 consumption:** Streamlit `app/services/` should query **mart** tables and **MetricFlow metrics** in `analytics_dev` (not reimplement KPI logic on `public` raw tables). `marts.yml` + semantic metric YAML define KPI meaning for humans, BI Assistant RAG, and AI CFO.

---

## Progress snapshot (May 2026)

**Phase 2a** — **done (100%).** **Phase 2b** — **done (100%).** See [Phase 2b](#phase-2b--ai-ready-metrics--semantic-layer). **Next:** [Phase 3](../phase-3/README.md) (Airflow).

| Area | Status |
|------|--------|
| dbt project (`staging` → `intermediate` → `marts`) | Done |
| Public staging (5 tables) + sources | Done |
| Seeds: `country_codes`, `instrument_mapping` | Done |
| Seed: `region_monthly_targets` + `stg_seed_region_monthly_targets` | Done |
| Seed staging + `source_seed.yml` tests | Done |
| Intermediate: trading, funding, affiliate cost | Done |
| Mart: `mrt_daily_user_activity` (incl. `daily_net_deposit_usd`) | Done |
| Mart: `mrt_user_lifetime` (LTV + activity summary) | Done |
| Mart: `mrt_company_monthly_performance` (regional actuals vs targets) | Done |
| Mart: `mrt_user_retention` (user grain; cohort curves via aggregation) | Done |
| Mart: `mrt_instrument_daily_kpi` (region × symbol × day) | Done |
| Layer documentation (`staging_public.yml`, `intermediate.yml`, `marts.yml`, …) | Done |
| Serving layer (`models/serving/`, subfolders per app) | Done |
| Serving: `mrt_company_daily_kpi` (`streamlit_dashboard/`) | Done |
| MetricFlow: 3 `semantic_models` + time spine | Done |
| MetricFlow: `metrics.yml` (**57** metrics: simple, ratio, cumulative, derived) | Done |
| `dbt parse` / semantic manifest validation | Done |
| Mart: `mrt_daily_affiliate` | **Won't do** (deferred — low value for current scope) |
| Mart: `mrt_region_daily_kpi` (optional v1) | **Deferred v1** (user-day + monthly sufficient) |
| `mrt_affiliate_summary` | **Deferred v2** |
| Notional USD volume | **Deferred** (no price on `trades`; see notes) |
| `mf query` smoke tests (sample KPI queries) | **Done** (May 2026) |
| Full `dbt test` suite | **Done** (**77** tests) |

---

## Phase 2b — AI-ready metrics & semantic layer

**Goal:** Finish the **semantic contract** Phase 4 needs — executive KPI marts plus **MetricFlow** metric definitions on dbt Core (free, local). Scale later by adding marts and YAML metrics without rewriting the Streamlit app.

**Status:** **Done** — semantic models, **57** metrics, `dbt parse`, and `mf query` smoke tests validated (May 2026).

**Prerequisite:** Phase 2a core marts stable and tested.

**Not in Phase 2b:** LLM code, Streamlit, forecasting, anomaly narratives (Phase 4 services). **Not required:** dbt Cloud Semantic Layer (hosted API). **Conversion** metrics (visit→buy style) — deferred until a funnel semantic model exists.

### Two layers

| Layer | Role |
|-------|------|
| **Marts (tables)** | Fast dashboard queries, CFO snapshots, forecasting inputs |
| **Semantic layer (YAML)** | Canonical metric names, dimensions, descriptions for BI Assistant + RAG |

Point `semantic_models` at mart models, not raw `public` tables.

### Marts v1 (build now)

| Mart | Grain | Purpose |
|------|-------|---------|
| **`mrt_company_daily_kpi`** | `effective_date` | Company KPI cards, trends, CFO daily snapshots |
| **`mrt_region_daily_kpi`** *(optional v1)* | `region` × `effective_date` | Regional comparison charts |

**Suggested `mrt_company_daily_kpi` columns:** `gross_revenue_usd`, `net_revenue_usd`, `active_users`, `gross_deposits_usd`, `withdrawals_usd`, `net_flow_usd`, `withdrawal_ratio` (document formulas in `marts.yml`).

Roll up from `mrt_daily_user_activity` or `int_fct_daily_user_activity` + `int_dim_users` as needed.

### Marts v2 (defer — add when needed)

| Mart | When |
|------|------|
| `mrt_affiliate_summary` | Affiliate performance table |
| `mrt_cohort_retention` (pre-aggregated) | Only if BI needs pre-built cohort curves |

*`mrt_instrument_daily_kpi` shipped in Phase 2b (core mart, not v2).*

### MetricFlow / semantic layer v1 — **shipped**

| Asset | File / model | Grain |
|-------|----------------|-------|
| `daily_user_activity` | `semantic_users_daily.yml` → `mrt_daily_user_activity` | user × day |
| `company_performance` | `semantic_company_monthly.yml` → `mrt_company_monthly_performance` | region × month |
| `daily_symbol_activity` | `semantic_instrument_daily.yml` → `mrt_instrument_daily_kpi` | symbol × region × day |
| Time spine | `semantic_models/utils/metricflow_time_spine.sql` | day |
| Metrics | `semantic_models/metrics.yml` | **57** metrics |

**Metric types in `metrics.yml`:**

| Type | Count | Examples |
|------|-------|----------|
| `simple` | 30 | `gross_revenue`, `net_revenue`, `active_users`, `*_total`, averages |
| `ratio` | 11 | `withdrawal_ratio`, `net_revenue_per_active_user`, `*_attainment` |
| `cumulative` | 9 | `cumulative_net_trade_revenue`, `*_mtd`, `trailing_28_day_net_revenue` |
| `derived` | 7 | `net_revenue_vs_target`, `*_vs_target_pct`, `symbol_cashback_pct_of_revenue` |

**Phase 2b canonical names** (for Phase 4 dashboard / RAG allowlist): `gross_revenue`, `net_revenue`, `active_users`, `gross_deposits`, `net_flow`, `withdrawal_ratio`, `net_revenue_vs_target`, `net_revenue_attainment`, etc.

**Dimension naming:** slice by `reporting_region` (not `region` entity) on user-day and instrument models to avoid cross-model type conflicts.

- **Validate:** `dbt parse` (semantic manifest) — **done**. Sample `mf query` — see [What's left](#whats-left-to-close-phase-2b).
- **Phase 4:** RAG loads `metrics.yml` + `marts.yml`; BI Assistant uses allowlisted metric names / compiled SQL only.

Reference: [How the dbt semantic layer works](https://www.getdbt.com/blog/how-the-dbt-semantic-layer-works) — use **MetricFlow on Core** for this project, not paid dbt Cloud SL unless requirements change.

### Phase 2b acceptance criteria

| Criterion | Status |
|-----------|--------|
| Phase 4 dashboard KPIs answerable from **one or two mart/serving queries** (no raw `public.*`) | **Done** — `mrt_company_daily_kpi` + user-day mart |
| Semantic metrics documented in YAML | **Done** — `metrics.yml` |
| `dbt parse` / semantic manifest valid | **Done** |
| `dbt test` on mart grains | **Done** — 77 tests |
| Multi-day simulation load validated | **Done** — see ROADMAP demo history |
| Sample `mf query` against Postgres | **Done** |

### `mf query` smoke tests (validated)

| Query | Group by | Result |
|-------|----------|--------|
| `daily_gross_trade_revenue_total` | `metric_time__day` | OK — daily rows May 2026 |
| `daily_gross_trade_revenue_total` | `user_day__reporting_region` | OK — America / Europe / Asia Pacific |
| `gross_revenue`, `withdrawal_ratio` | `metric_time__month` | OK — e.g. withdrawal_ratio ≈ 0.31 |
| `net_revenue_vs_target_pct` | `region_month__reporting_region` | OK — variance by region |

Commands and Windows UTF-8 tip: `docs/runbook.md` (MetricFlow section).

### Deferred (not required to close Phase 2)

- `mrt_region_daily_kpi`, `mrt_affiliate_summary`, conversion metrics, semantic model on `mrt_company_daily_kpi` (dashboard uses serving mart + user-day metrics today).

---

## Design notes (from implementation review)

### Simulator behavior (affects LTV / churn metrics)

- Each batch day, **all users** with `signup_date <= batch_date` are treated as **active** (`simulation/generate_daily.py`).
- There is **no churn** and no “stopped trading” state; users are never removed from the active pool.
- Trade count per user per day is **Poisson** (can be **zero** on a day, but the user remains eligible next day).
- If multiple days are loaded, **`MAX(trade_ts)`** often equals the **latest loaded batch date** for most users who ever traded — that is expected, not evidence of daily trading by everyone.

**Implication:** Build **cumulative lifetime** metrics from daily marts; do not interpret retention/churn LTV like a production CRM until Phase 1 adds churn or inactivity rules.

### Notional volume (out of scope for now)

- Raw `trades` has `volume_lots` only — no fill price / spot.
- `instrument_mapping.symbol_size` documents contract size for future use; **do not** ship USD notional marts until prices exist (seed or external rates).
- **In scope:** economics per lot via `symbol_trade_cost_per_lot`, `symbol_cashback_per_lot` in `int_fct_daily_trading`.

### LTV definitions (use explicit labels in YAML)

| Metric | Suggested column / mart | Meaning |
|--------|-------------------------|---------|
| Trade revenue LTV | `lifetime_trade_revenue_usd` | Sum of `daily_trade_revenue_usd` |
| Net trade LTV | `lifetime_net_trade_revenue_usd` | Sum of `daily_net_trade_revenue_usd` (affiliate cost on first-trade day) |
| Funding LTV | `lifetime_net_deposit_usd` | Sum of `daily_net_deposit_usd` (wallet flow, not P/L) |

Do not combine funding and trade revenue into one “LTV” without documenting both.

---

## Mart layer — planned models

All marts materialize as **tables** under `analytics_dev` (see `dbt_project.yml`). Document each in `models/marts/marts.yml`.

**Scope note:** Affiliate-day mart (`mrt_daily_affiliate`) is **out of scope for now**; affiliate economics remain in `int_fct_affiliates_cost` and user-day / lifetime marts.

### 1. `mrt_daily_user_activity` — **done**

| | |
|--|--|
| **Grain** | `user_id` × `effective_date` |
| **Purpose** | Daily drill-down: trading economics, funding, affiliate cost on acquisition day, user dims (VIP, channel, country, region). |
| **Upstream** | `int_fct_daily_trading`, `int_fct_daily_funding`, `int_fct_affiliates_cost`, `stg_public_users`, `country_codes` |
| **Key columns** | `daily_gross_deposit_usd`, `daily_withdrawal_usd`, `daily_net_deposit_usd`, `daily_trade_revenue_usd`, `daily_net_trade_revenue_usd`, … |

---

### 2. `mrt_user_lifetime` — **done**

| | |
|--|--|
| **Grain** | `user_id` (one row per customer) |
| **Purpose** | User-level LTV and activity summary for rankings and BI drill-downs. |
| **Upstream** | `mrt_daily_user_activity` (+ optional `stg_public_users` for static attrs) |

**Suggested columns**

- Keys / dims: `user_id`, `signup_date`, `user_group`, `acquisition_channel`, `country_name`, `region`
- Activity: `first_activity_date`, `last_activity_date`, `days_with_trades`, `days_with_any_activity`
- Lifetime sums: `lifetime_trade_revenue_usd`, `lifetime_net_trade_revenue_usd`, `lifetime_gross_deposit_usd`, `lifetime_withdrawal_usd`, `lifetime_net_deposit_usd`, `lifetime_affiliate_cost_usd`
- Optional: `lifetime_trade_count` from `int_fct_daily_trading` if needed

**Tests:** `user_id` unique + not_null.

**Implemented:** `dbt/models/marts/mrt_user_lifetime.sql` — aggregates from `int_fct_daily_user_activity` + `int_fct_daily_trading` with dims from `int_dim_users`.

---

### 3. `mrt_daily_affiliate` — **won't do** (deferred)

| | |
|--|--|
| **Grain** | `affiliate_id` × `effective_date` |
| **Purpose** | Affiliate performance: acquired users, costs, attributed trading/funding on that day. |
| **Status** | **Deferred** — not building for Phase 2; affiliate cost already in user-day and lifetime marts. Revisit if affiliate reporting becomes a priority. |

---

### 4. `mrt_company_monthly_performance` — **done** (regional company performance vs targets)

| | |
|--|--|
| **Grain** | `region` × `effective_month` |
| **Purpose** | Executive / regional KPIs with **monthly actual vs plan** (active users, net trade revenue, gross deposits). |
| **Upstream** | `int_fct_daily_user_activity`, `int_dim_users`, `stg_seed_region_monthly_targets` |
| **Implemented** | `dbt/models/marts/mrt_company_monthly_performance.sql` |

**Actuals (monthly roll-up)**

- `actual_active_users` — distinct users with activity in the region/month
- `actual_net_trade_revenue_usd` — sum of `daily_trade_revenue_usd - affiliate_cost_usd`
- `actual_gross_deposit_usd` — sum of `daily_gross_deposit_usd`

**Targets (seed — do not hardcode in SQL)**

`seeds/region_monthly_targets.csv` with `start_date` / `end_date` (change plans by adding rows):

| Column | Purpose |
|--------|---------|
| `region` | `America`, `Europe`, `Asia Pacific` |
| `start_date`, `end_date` | Inclusive range; `effective_month` must fall between |
| `target_monthly_active_traders` | Planned active traders per month |
| `target_monthly_net_trade_revenue_usd` | Planned net trade revenue per month |
| `target_monthly_gross_deposit_usd` | Planned gross deposits per month |

Staging: `stg_seed_region_monthly_targets`. Tests in `source_seed.yml` and `marts.yml` (`not_null` on mart columns).

**Optional later:** daily region mart with prorated targets, variance / attainment columns.

---

### 5. `mrt_user_retention` — **done**

| | |
|--|--|
| **Grain** | `user_id` (one row per customer) |
| **Purpose** | Signup-cohort and return-to-activity flags at day offsets (0, 1, 7, 30); aggregate in Phase 4 for retention curves. |
| **Upstream** | `int_dim_users`, `int_fct_daily_trading`, `int_fct_daily_user_activity` |
| **Implemented** | `dbt/models/marts/mrt_user_retention.sql` |

**Caveat:** Simulator has no churn; treat as **return-to-activity** rates, not CRM churn. Document in `marts.yml`.

**Optional later:** pre-aggregated `mrt_cohort_retention` if BI needs cohort × offset as a table (v2).

---

## Supporting seeds (current + planned)

| Seed | Status | Role |
|------|--------|------|
| `country_codes` | Done | Country → region for regional rollups |
| `instrument_mapping` | Done | Cost/cashback per lot, contract size (notional later) |
| `region_monthly_targets` | Done | Monthly regional KPI plans for `mrt_company_monthly_performance` |

Instrument seed implemented as `instrument_mapping` (not `instrument_config.csv`); column names differ from early draft below but intent is the same.

### Instrument seed (reference — implemented)

- `symbol_name`, `symbol_trade_cost_per_lot`, `symbol_cashback_per_lot`, `symbol_size`
- Used in `int_fct_daily_trading` for cost/cashback; **not** for USD notional until prices exist.

---

## Layer checklist (non-mart)

| Layer | Purpose | Status |
|-------|---------|--------|
| **Staging (public)** | Thin views on `src_public` | Done |
| **Staging (seed)** | `stg_seed_*` over seeds | Done |
| **Intermediate** | Trade economics, funding, affiliate cost | Done |
| **Marts** | User-day, lifetime, company monthly, retention, instrument daily | **Done** (5 core marts) |
| **Serving** | `mrt_company_daily_kpi` for dashboard | **Done** |
| **Semantic layer** | 3 semantic models + 57 metrics | **Done** |
| **dbt tests** | Seeds + grain keys on marts/serving | **Done** (77 tests) |
| **dbt docs** | `marts.yml` + KPI formulas in descriptions | Done; extend when new marts added |

---

## Outputs / acceptance criteria

- **Reusable** KPI logic in marts and semantic metrics (not one-off SQL in apps) — **done**.
- **Phase 2b:** company daily KPI **serving** mart + MetricFlow metrics for Phase 4 dashboard and AI — **done** (`mf query` validated).
- **Core marts** at stable grains (user-day, user lifetime, **region-month with targets**, user retention, instrument daily) — **done**.
- **Tested** transformations (`dbt test` on grains and seeds) — **done** (77 tests).
- **Documented** models and lineage (`dbt docs generate` locally).
- Validated against **multi-day** simulator loads — **done** (2026-05-01 → 2026-05-25).

---

## Suggested build order

**Phase 2a (done)**

1. ~~Seed `region_monthly_targets` + staging~~
2. ~~Core marts (user-day, lifetime, company monthly, user retention)~~
3. Expand multi-day validation + `dbt test`

**Phase 2b (done)**

4. ~~**`mrt_company_daily_kpi`**~~ — done (serving)
5. ~~**MetricFlow:** `semantic_models` + `metrics.yml`~~ — done (57 metrics)
6. ~~**`mf query` smoke tests** + runbook samples~~ — done
7. Optional: **`mrt_region_daily_kpi`** — deferred v1

**v2 (after Phase 4)**

8. `mrt_affiliate_summary`, conversion metrics, extra semantic models — YAML/tables only

---

## Tools (expected)

dbt Core, **dbt-metricflow** (MetricFlow), SQL, PostgreSQL, Python (optional for tooling/scripts).

---

## Notes for agents

- Name marts for **business consumption** (stable for Phase 4 Streamlit services).
- Align **grain** explicitly in YAML (user-day, user, region-month; affiliate-day only if revived).
- Keep KPI formulas in **column descriptions** (e.g. net deposit = deposits − withdrawals).
- Phase 1 **`trades.volume_lots`** stays in lots; optional `daily_volume_lots` in user mart is fine; **USD notional** waits for prices.
- Regional company performance **must** join targets from **`region_monthly_targets`**, not constants in SQL.
- Simulator has no churn — lifetime marts are **cumulative-to-date**, not predictive LTV.
