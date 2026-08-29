---
title: Semantic layer and metric trust
parent: Work
nav_order: 2
eyebrow: Financial analytics
lede: Compute each metric once in dbt, test the grain, and publish it through MetricFlow so a dashboard, a chat answer and a report cannot drift apart.
tech: dbt Core · MetricFlow · SQL · Postgres
description: Three semantic models and 57 metrics on tested marts, including the path from raw trades to net revenue.
has_toc: false
---

<section class="case-block" markdown="1" id="context">
<p class="eyebrow">01 — Context</p>
<h2>What problem this addresses</h2>

<p>The same commercial figure — net revenue, active users, withdrawal ratio — is easy to define differently in a dashboard, a chat answer and a report. Once that happens, no amount of chart polish helps. The decision-maker is comparing three numbers that only look like the same KPI.</p>

<p>This is the part of the project I own outright and would defend line by line in an interview. Everything else exists so that this layer has somewhere to live and something to serve.</p>
</section>

<section class="case-block" markdown="1" id="approach">
<p class="eyebrow">02 — Approach</p>
<h2>How the problem was approached</h2>

<p>Compute each metric once in dbt, test the grain, and publish it through MetricFlow so every consumer reads the same definition.</p>

<p>The executive dashboard and the BI Assistant use different query paths. They cannot drift, because both resolve back to the same intermediate model.</p>
</section>

<section class="case-block" markdown="1" id="architecture">
<p class="eyebrow">03 — Architecture</p>
<h2>How the system works</h2>

<p>Three MetricFlow semantic models sit on top of core marts:</p>

<ul>
  <li><code>daily_user_activity</code> over <code>mrt_daily_user_activity</code> — ten measures, dimensions for user group, acquisition channel, country, region, signup date and user id</li>
  <li><code>daily_symbol_activity</code> over <code>mrt_instrument_daily_kpi</code> — nine measures covering volume, trade count and revenue by instrument</li>
  <li><code>company_performance</code> over <code>mrt_company_monthly_performance</code> — six measures pairing actuals with targets</li>
</ul>

<p>From those, <a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/semantic_models/metrics.yml"><code>metrics.yml</code></a> defines <strong>57 metrics</strong>: 30 simple, 11 ratio, 9 cumulative and 7 derived. Cumulative metrics include month-to-date aggregates and 28-day rolling windows, which is why the project also maintains a <code>metricflow_time_spine</code> model spanning 2025 to 2028 — cumulative and window metrics need a dense date spine to be correct across days with no activity.</p>

<p>Note what does <strong>not</strong> have a semantic model: <code>mrt_user_lifetime</code> and <code>mrt_user_retention</code>. Both are at user grain and are consumed as tables. Wrapping them in metrics would imply they aggregate cleanly over time, and they do not.</p>
</section>

<section class="case-block" markdown="1" id="implementation">
<p class="eyebrow">04 — Implementation</p>
<h2>Tracing one metric end to end</h2>

<p>Ask the BI Assistant for <code>net_revenue</code> and here is what actually produced the number.</p>

<p><strong>1. Raw and seed.</strong> <code>trades</code> gives client profit and loss and volume in lots. The <code>instrument_mapping</code> seed gives per-lot trading cost and per-lot cashback for each symbol.</p>

<p><strong>2. Trading economics</strong>, in <a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/intermediate/int_fct_daily_trading.sql"><code>int_fct_daily_trading.sql</code></a>. The broker's profit is the client's loss, so <code>company_pnl_usd</code> is the negation of client PnL. Trading cost is volume times the per-lot rate. Cashback is uplifted for VIP clients on a sliding scale by instrument group — 20 percent on FX majors, 15 percent on metals, 10 percent on crypto. Then:</p>

```sql
company_pnl_usd + trade_cost_usd - adjusted_cashback_per_trade_usd as trade_revenue_usd
```

<p><strong>3. Aggregation to user and day</strong> in <code>int_fct_daily_user_activity</code>, which combines trading with funding and affiliate cost onto one spine.</p>

<p><strong>4. Acquisition cost deduction</strong>, in <a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/dbt/models/marts/mrt_daily_user_activity.sql"><code>mrt_daily_user_activity.sql</code></a>:</p>

```sql
f.daily_trade_revenue_usd - f.affiliate_cost_usd as daily_net_trade_revenue_usd
```

<p><strong>5. Exposure as a measure and metric.</strong> The semantic model declares <code>daily_net_trade_revenue</code> as a sum measure; <code>metrics.yml</code> publishes it as the metric <code>net_revenue</code>.</p>

<p>The important property is at the end. The executive dashboard reads <code>net_revenue_usd</code> from the serving mart, and the BI Assistant reads the <code>net_revenue</code> metric through MetricFlow. <strong>Two different consumers, two different query paths, one definition</strong> — because both resolve back to the same intermediate model. They cannot drift apart, and there is no place for a "net revenue" that means something slightly different in one tool.</p>

<h3>Why <code>withdrawal_ratio</code> exists twice</h3>

<p>It is a column in <code>mrt_company_daily_kpi</code> and also a ratio metric in MetricFlow. That looks like duplication and is not.</p>

<p>The mart column is guarded:</p>

```sql
case when sum(daily_gross_deposit_usd) > 0
     then sum(daily_withdrawal_usd) / sum(daily_gross_deposit_usd)
     else null end as withdrawal_ratio
```

<p>On a day with no deposits the honest answer is "undefined", not zero and not infinity. Returning <code>null</code> means the sparkline shows a gap instead of a spike that would send someone chasing a phantom problem.</p>

<p>The MetricFlow metric exists for a different reason: it is defined as a ratio of two measures, so when you group by region or by month, it recomputes as <strong>sum of withdrawals over sum of deposits at that grain</strong>. A pre-computed daily column cannot do that — averaging daily ratios across a month gives a different, wrong answer, weighting a quiet Sunday the same as a heavy Monday. You need the column for the fixed daily dashboard and the metric for arbitrary slicing.</p>

<h3><code>net_revenue_vs_target</code> versus <code>net_revenue_attainment</code></h3>

<p>Both compare actuals to plan and they are not interchangeable.</p>

<p><code>net_revenue_vs_target</code> is a derived metric, <code>actual - target</code>, in dollars. It answers "how much are we short". It is the right number when you need to size a gap, and it is meaningless when comparing a large region to a small one.</p>

<p><code>net_revenue_attainment</code> is a ratio, <code>actual / target</code>. It answers "how are we tracking as a fraction of plan", and it is the one that lets you rank regions of different sizes fairly.</p>

<p>There is also <code>net_revenue_vs_target_pct</code>, which wraps the difference over target with a <code>NULLIF(target, 0)</code> guard so a region with no plan set produces a null rather than a division error.</p>
</section>

<section class="case-block" markdown="1" id="results">
<p class="eyebrow">05 — Results / Evidence</p>
<h2>What makes the numbers trustworthy</h2>

{% include metrics.html %}

<p><strong>83 tests</strong> defined in YAML — 68 across the models and 15 on the seeds. Broken down: 61 <code>not_null</code>, 10 <code>unique</code>, 7 <code>dbt_utils.unique_combination_of_columns</code> grain assertions, 4 <code>accepted_values</code>, and 1 <code>relationships</code> test tying trading facts back to the user dimension.</p>

<p>The grain tests are the ones that matter most. Every mart claims a grain in its YAML documentation, and each claim has a test enforcing it. A fan-out from a bad join is the single most common way a revenue number silently doubles, and it is caught here rather than noticed in a board meeting.</p>

<p>The <code>relationships</code> test earns its place too: if a trade appears for a user who is not in the dimension, the join in <code>mrt_daily_user_activity</code> is an inner join and that revenue would silently disappear. The test turns silent loss into a loud failure.</p>

<p>Because <code>dbt_test</code> is a separate task in the Airflow DAG and sits upstream of the CFO report, a failing test stops the pipeline before anyone is emailed a number.</p>
</section>

<section class="case-block" markdown="1" id="reflection">
<p class="eyebrow">06 — Reflection</p>
<h2>Limitations I will state before you find them</h2>

<p><strong>Retention here is activity-based, not churn.</strong> <code>mrt_user_retention</code> flags whether a user was active again at day 1, 7 and 30 after signup. It does not model account closure, because the simulator does not produce one. Presented to a stakeholder, this is "did they come back", not "did we lose them", and conflating those two is how retention dashboards end up lying.</p>

<p><strong>Per-client trading volume is not answerable.</strong> Volume and trade count live only in <code>daily_symbol_activity</code>, whose grain is symbol by region by day with no user id. So "top ten clients by volume" cannot be answered today. It needs a new mart joining trades to users, tracked as item I-4 in <a href="https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/IMPROVEMENTS.md">IMPROVEMENTS.md</a>. Rather than let the BI Assistant approximate it, the allowlist simply cannot express the question — which I consider the correct failure mode.</p>

<p><strong>Clients are identified by id, not name.</strong> Rankings are readable to me and not to an executive. It is a small dimension away and deliberately not done yet.</p>
</section>

<section class="case-block" markdown="1" id="transparency">
<p class="eyebrow">07 — Transparency</p>
<h2>What I built directly</h2>

<p>The dbt models, tests and metric YAML are mine. Grain decisions, the split of facts by process, the business logic in trading economics, and every metric definition — this is the layer I would sit and defend. The Streamlit surfaces that consume it were built with an AI coding agent under my direction. The full split is on <a href="{{ '/05-ownership-and-cursor-workflow.html' | relative_url }}">How this project was built</a>.</p>
</section>
