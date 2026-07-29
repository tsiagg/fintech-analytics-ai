# Project improvements backlog

A small, living list of **future updates we could make** — separate from the phased
[ROADMAP.md](./ROADMAP.md) (which tracks the committed build). Use this file to
capture ideas, refinements, and tech-debt items as they come up, so nothing gets
lost between phases.

**Last updated:** 2026-06-22

## How to use this file

1. Add a row to the [Backlog](#backlog) table when an idea surfaces (one line is fine).
2. Set **Priority** (P1 = soon / high value, P2 = nice-to-have, P3 = someday) and a rough **Effort** (S / M / L).
3. When you start work, set **Status** to *In progress*; when shipped, set *Done* + the date, and (if it was a committed item) update `ROADMAP.md` too.
4. Keep the detail notes under [Details](#details) short — link to code or a phase README instead of duplicating.

## Backlog

| ID | Area | Improvement | Why it matters | Effort | Priority | Status |
|----|------|-------------|----------------|--------|----------|--------|
| I-1 | BI Assistant | Harden the Pro planning path: larger planner token budget, never use `reasoning` text as JSON, retry on the other tier when the plan won't parse | "Why/root-cause/spike" questions kept failing on Pro | S | P1 | **Done (2026-06-19)** |
| I-2 | BI Assistant | Relax refusal guidance for "why / driver" questions → plan a breakdown instead of refusing | Pro was refusing instead of analysing | S | P1 | **Done (2026-06-19)** |
| I-3 | AI CFO | Multi-section **report orchestrator** (runs a fixed set of pre-defined queries per section, then stitches into a template) | One-shot planner can't produce a full executive report; needed for AI CFO | L | P1 | Not started |
| I-4 | dbt / semantic | Per-client **trading volume & trade count** (join trades → users) so client-level performance is answerable | Volume/trades live only in the symbol model (no `user_id`); blocks "top clients by volume" | M | P2 | Not started |
| I-5 | BI Assistant | Input/context guards: trim the catalog + size the data table dynamically; friendly message when a question is too broad | Avoid hitting model context limits; better UX than a generic refusal | M | P2 | Not started |
| I-6 | BI Assistant | Multi-metric period-over-period (current `_period_over_period` only handles the first metric) | WoW/MoM across several KPIs in one answer | M | P2 | Not started |
| I-7 | BI Assistant | Cost control: only retry on the alternate tier when the first attempt truly returned empty/invalid JSON | Keep within the < $15/mo target as usage grows | S | P2 | Not started |
| I-8 | dbt / semantic | Add `country_name` to the symbol model (or a region↔country bridge) so volume/trades are sliceable by country | Enables "volume by country" and country-concentration views | M | P3 | Not started |
| I-9 | dbt / semantic | Client **display name** dimension (not just `user_id`) | Friendlier client rankings in reports | S | P3 | Not started |
| I-10 | Deployment / demo | Expose the local Streamlit app publicly via a **Cloudflare Tunnel** (named tunnel on a custom domain) for live demonstrations | Share the running app with reviewers/recruiters without deploying to a host | S | P2 | Not started |
| I-11 | Daily Insights | **Proactive insights orchestrator** — daily anomaly scan, benchmarking, top-client driver attribution, severity alerts; Streamlit page + Airflow task | Complements reactive BI Assistant and monthly AI CFO with scheduled "what moved and why" cards (e.g. gross deposit spike driven by a big client) | L | P1 | Not started |

## Details

Only items that need more than the one-liner above.

### I-3 — AI CFO report orchestrator
- The BI Assistant is a **single-question** engine: one plan → one query set → one explainer (capped output, 40-row tables). A 7-section executive report exceeds that by design.
- Proposed approach: a `cfo_engine` that owns a **template of sections**, each backed by one or more governed MetricFlow queries, runs them, then composes the narrative (reusing the existing analysis-context + explainer helpers in `app/services/bi_engine.py`).
- Aligns with the Phase 4 **AI CFO** work already on the roadmap.

### I-4 — Per-client volume mart
- `daily_symbol_activity` has `volume_lots` / `trade_count` but its grain is symbol × region × day with **no `user_id`** — so per-client volume can't be joined today.
- Needs a new mart (trades joined to users) + a semantic model exposing `user_id` alongside volume/trades. Add YAML/tables only; no app rewrite.

### I-11 — Daily Insights orchestrator
- **Not** a free-roaming agent loop — follow the same pattern as `reporting/` and AI CFO: Python computes, LLM only narrates (optional), Streamlit displays.
- **Detect:** extend `reporting/anomalies.py` (z-score, rule flags) on `mrt_company_daily_kpi`; flag moves only when delta and/or z-score cross thresholds.
- **Decompose:** WoW (or DoD) driver attribution — rank `user_id`, `reporting_region`, `user_group`, `acquisition_channel` via `mrt_daily_user_activity` / MetricFlow `gross_deposits`, `net_revenue`, etc.; compute each driver's `contribution_usd` and `% of company delta`; tag concentration when top N clients explain most of the move.
- **Benchmark:** historical (30d mean / z-score), target pace (`region_monthly_targets`), peer slices (region vs company, VIP vs Normal).
- **Alerts:** severity tiers (info / watch / risk) on top of structured insight objects — not LLM-judged.
- **Deliverables:** new `insights/` package (mirror `reporting/`), Postgres table (e.g. `insights_daily_runs`), Airflow task after `generate_cfo_report` in `daily_fintech_analytics.py`, Streamlit page (e.g. `app/pages/4_Daily_Insights.py`) with category cards (Funding, Revenue, Activity, Risk), filters by severity, and optional Plotly driver charts.
- **v1 scope (no new marts):** company KPI anomalies + per-client funding/revenue drivers. Per-client **volume** rankings blocked until **I-4**; friendlier client labels until **I-9**.
- **Phases:** (1) MVP — JSON store + basic cards; (2) LLM one-liner per card + richer UI; (3) regional driver trees + volume after I-4.

### I-10 — Public demo via Cloudflare Tunnel
- Goal: share the locally running Streamlit app (`http://localhost:8501`) on a public URL for demos, without deploying to a cloud host.
- Quick (no domain): `cloudflared tunnel --url http://localhost:8501` gives a temporary `*.trycloudflare.com` URL.
- Stable (custom domain): create a **named tunnel** (`cloudflared tunnel create`), map a DNS route to it (`cloudflared tunnel route dns <tunnel> demo.<your-domain>`), and run it via a `config.yml` ingress pointing at `localhost:8501`.
- Considerations: keep it **demo-only** (the app reads local Postgres marts and uses the OpenRouter key); add Cloudflare Access (email/PIN) if the link is shared widely, and never expose the `.env`/API key. Fits naturally with Phase 5 portfolio/demo work.

### I-1 / I-2 — BI Assistant Pro robustness (shipped)
- Planner token budget raised; JSON requests no longer fall back to `reasoning` prose; planner now retries on the alternate tier; "why/driver" questions plan a breakdown instead of refusing.
- See `app/services/ai_client.py` and `app/services/bi_engine.py`.
