---
title: Semantic layer and metric trust
parent: Work
nav_order: 2
---

# Semantic layer and metric trust

This is the part of the project I own outright and would defend line by line in an interview. Everything else exists so that this layer has somewhere to live and something to serve.

## What is in it

Three MetricFlow semantic models sit on top of core marts:

- `daily_user_activity` over `mrt_daily_user_activity` — ten measures, dimensions for user group, acquisition channel, country, region, signup date and user id
- `daily_symbol_activity` over `mrt_instrument_daily_kpi` — nine measures covering volume, trade count and revenue by instrument
- `company_performance` over `mrt_company_monthly_performance` — six measures pairing actuals with targets

From those, [`metrics.yml`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/semantic_models/metrics.yml) defines **57 metrics**: 30 simple, 11 ratio, 9 cumulative and 7 derived. Cumulative metrics include month-to-date aggregates and 28-day rolling windows, which is why the project also maintains a `metricflow_time_spine` model spanning 2025 to 2028 — cumulative and window metrics need a dense date spine to be correct across days with no activity.

Note what does **not** have a semantic model: `mrt_user_lifetime` and `mrt_user_retention`. Both are at user grain and are consumed as tables. Wrapping them in metrics would imply they aggregate cleanly over time, and they do not.

## Tracing one metric end to end

Ask the BI Assistant for `net_revenue` and here is what actually produced the number.

**1. Raw and seed.** `trades` gives client profit and loss and volume in lots. The `instrument_mapping` seed gives per-lot trading cost and per-lot cashback for each symbol.

**2. Trading economics**, in [`int_fct_daily_trading.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql). The broker's profit is the client's loss, so `company_pnl_usd` is the negation of client PnL. Trading cost is volume times the per-lot rate. Cashback is uplifted for VIP clients on a sliding scale by instrument group — 20 percent on FX majors, 15 percent on metals, 10 percent on crypto. Then:

```sql
company_pnl_usd + trade_cost_usd - adjusted_cashback_per_trade_usd as trade_revenue_usd
```

**3. Aggregation to user and day** in `int_fct_daily_user_activity`, which combines trading with funding and affiliate cost onto one spine.

**4. Acquisition cost deduction**, in [`mrt_daily_user_activity.sql`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/mrt_daily_user_activity.sql):

```sql
f.daily_trade_revenue_usd - f.affiliate_cost_usd as daily_net_trade_revenue_usd
```

**5. Exposure as a measure and metric.** The semantic model declares `daily_net_trade_revenue` as a sum measure; `metrics.yml` publishes it as the metric `net_revenue`.

The important property is at the end. The executive dashboard reads `net_revenue_usd` from the serving mart, and the BI Assistant reads the `net_revenue` metric through MetricFlow. **Two different consumers, two different query paths, one definition** — because both resolve back to the same intermediate model. They cannot drift apart, and there is no place for a "net revenue" that means something slightly different in one tool.

## Judgement calls worth explaining

### Why `withdrawal_ratio` exists twice

It is a column in `mrt_company_daily_kpi` and also a ratio metric in MetricFlow. That looks like duplication and is not.

The mart column is guarded:

```sql
case when sum(daily_gross_deposit_usd) > 0
     then sum(daily_withdrawal_usd) / sum(daily_gross_deposit_usd)
     else null end as withdrawal_ratio
```

On a day with no deposits the honest answer is "undefined", not zero and not infinity. Returning `null` means the sparkline shows a gap instead of a spike that would send someone chasing a phantom problem.

The MetricFlow metric exists for a different reason: it is defined as a ratio of two measures, so when you group by region or by month, it recomputes as **sum of withdrawals over sum of deposits at that grain**. A pre-computed daily column cannot do that — averaging daily ratios across a month gives a different, wrong answer, weighting a quiet Sunday the same as a heavy Monday. You need the column for the fixed daily dashboard and the metric for arbitrary slicing.

### `net_revenue_vs_target` versus `net_revenue_attainment`

Both compare actuals to plan and they are not interchangeable.

`net_revenue_vs_target` is a derived metric, `actual - target`, in dollars. It answers "how much are we short". It is the right number when you need to size a gap, and it is meaningless when comparing a large region to a small one.

`net_revenue_attainment` is a ratio, `actual / target`. It answers "how are we tracking as a fraction of plan", and it is the one that lets you rank regions of different sizes fairly.

There is also `net_revenue_vs_target_pct`, which wraps the difference over target with a `NULLIF(target, 0)` guard so a region with no plan set produces a null rather than a division error.

## What makes the numbers trustworthy

**83 tests** defined in YAML — 68 across the models and 15 on the seeds. Broken down: 61 `not_null`, 10 `unique`, 7 `dbt_utils.unique_combination_of_columns` grain assertions, 4 `accepted_values`, and 1 `relationships` test tying trading facts back to the user dimension.

The grain tests are the ones that matter most. Every mart claims a grain in its YAML documentation, and each claim has a test enforcing it. A fan-out from a bad join is the single most common way a revenue number silently doubles, and it is caught here rather than noticed in a board meeting.

The `relationships` test earns its place too: if a trade appears for a user who is not in the dimension, the join in `mrt_daily_user_activity` is an inner join and that revenue would silently disappear. The test turns silent loss into a loud failure.

Because `dbt_test` is a separate task in the Airflow DAG and sits upstream of the CFO report, a failing test stops the pipeline before anyone is emailed a number.

## Limitations I will state before you find them

**Retention here is activity-based, not churn.** `mrt_user_retention` flags whether a user was active again at day 1, 7 and 30 after signup. It does not model account closure, because the simulator does not produce one. Presented to a stakeholder, this is "did they come back", not "did we lose them", and conflating those two is how retention dashboards end up lying.

**Per-client trading volume is not answerable.** Volume and trade count live only in `daily_symbol_activity`, whose grain is symbol by region by day with no user id. So "top ten clients by volume" cannot be answered today. It needs a new mart joining trades to users, tracked as item I-4 in [IMPROVEMENTS.md](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/IMPROVEMENTS.md). Rather than let the BI Assistant approximate it, the allowlist simply cannot express the question — which I consider the correct failure mode.

**Clients are identified by id, not name.** Rankings are readable to me and not to an executive. It is a small dimension away and deliberately not done yet.
