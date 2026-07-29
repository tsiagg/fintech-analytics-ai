# Phase 1 — Data engineering (simulation system)

**Parent brief:** See `../Analytics Project Summary - Fintech Simulation.docx` (full vision and data model).

**Status:** Complete for current scope. Orchestration (Airflow) is deferred to [Phase 3](../phase-3/README.md).

## Goal

Create a realistic **fintech simulation engine** that generates **new business data every day** (not a one-off CSV dump), persisted in PostgreSQL as the raw layer for dbt.

## What to build

| Component | Purpose |
|-----------|---------|
| **Python synthetic data generator** | Emit users, trades, deposits, withdrawals aligned to the conceptual schema (Users, Affiliates, Trades, Deposits, Withdrawals). |
| **Scenario engine** | Drive business conditions (e.g. market crash, high volatility, marketing campaign, stable market). Scenarios influence trading volume, deposits/withdrawals, user growth, PnL. |
| **PostgreSQL** | Persist **raw** generated data (single source of truth for downstream phases). |
| **Manual / CLI daily loads** | `python -m simulation --date YYYY-MM-DD` (see `docs/runbook.md`). Sufficient until Phase 3 automates the pipeline. |

**Not in Phase 1 (moved to Phase 3):** Airflow DAGs, scheduled jobs, dbt orchestration.

## Conceptual entities (from brief)

- **Users** (dimension): `user_id`, `signup_date`, `country_code`, `vip_status` (nullable), `affiliate_id`
- **Affiliates** (dimension): `affiliate_id`, `country_code`, `tier`, `acquisition_cost` — raw codes join to **dbt geography seed** in Phase 2 for name/continent.
- **Trades** (fact): `trade_id`, `user_id`, `symbol`, `volume_lots`, `pnl`, `trade_ts`, `batch_date`
- **Deposits** (fact): `deposit_id`, `user_id`, `amount`, `status`, `payment_provider`, `deposit_ts`, `batch_date`
- **Withdrawals** (fact): `withdrawal_id`, `user_id`, `amount`, `status`, `payment_provider`, `withdrawal_ts`, `batch_date`

## Outputs / acceptance criteria

- Realistic, **repeatable** daily batches (deterministic seeds via `--seed` or date-derived default).
- **Growing** dataset over calendar time when multiple batch dates are loaded in order.
- Raw tables and generator documented; **idempotent** re-runs per `batch_date` / `signup_date`.
- Phase 2 can experiment immediately against loaded raw data (no Airflow required yet).

## Tools (expected)

Python, PostgreSQL, Docker, SQL. CLI documented in `docs/runbook.md`.

## Notes for agents

- Prefer **idempotent daily loads** (e.g. batch date/partition) so re-runs do not corrupt facts.
- Keep **raw** tables wide enough for Phase 2 staging models; avoid premature BI logic here.
- Document scenario parameters so Phase 4 anomaly/scenario detection can reuse definitions (`python -m simulation --list-scenarios`).
- **`trades.volume_lots`** is in standard lots; notional USD and economics belong in Phase 2 (instrument config seed).
