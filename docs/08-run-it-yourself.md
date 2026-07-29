---
title: Run it yourself
nav_order: 9
---

# Run it yourself

Everything runs locally. The dashboard needs no API key; only the BI Assistant and the CFO report do.

You need Docker Desktop and Python 3.11. Commands are PowerShell, run from the project root.

## 1. Configure

```powershell
Copy-Item .env.example .env
Copy-Item dbt\profiles.example.yml dbt\profiles.yml
```

The defaults in `.env` work as-is for a local run. Leave `LLM_API_KEY` empty unless you want the AI pages; an [OpenRouter](https://openrouter.ai/keys) key with a spend limit is enough.

## 2. Start the stack

```powershell
docker compose -f infra/docker-compose.yml up -d
```

That brings up the fintech Postgres warehouse and Airflow 3 on LocalExecutor. Airflow is at [localhost:8080](http://localhost:8080), user `airflow`, password `airflow`. The `daily_fintech_analytics` DAG is unpaused on creation and will begin backfilling from its start date one day at a time.

If you would rather not wait for Airflow, the next two steps do the same work by hand.

## 3. Generate some history

```powershell
.\.venv\Scripts\Activate.ps1
python -m simulation --date 2026-05-15
python -m simulation --date 2026-05-16
python -m simulation --date 2026-05-17
```

Each run is idempotent for its date, so re-running a day replaces it. Two useful flags: `--list-scenarios` prints the six available scenarios, and `--scenario market_crash` forces a specific one, which is the quickest way to give the dashboard something interesting to show.

Generate at least three or four weeks if you want the week-over-week comparisons, rolling metrics and anomaly detection to have anything to work with.

## 4. Build and test the warehouse

```powershell
dbt deps --project-dir dbt --profiles-dir dbt
dbt run  --project-dir dbt --profiles-dir dbt
dbt test --project-dir dbt --profiles-dir dbt
```

All 83 tests should pass. If a grain test fails, something upstream is producing duplicates — that is the test doing its job.

To query the semantic layer directly:

```powershell
$env:PYTHONIOENCODING='utf-8'
mf query --metrics daily_gross_trade_revenue_total --group-by metric_time__day
```

## 5. Open the app

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8501
```

[localhost:8501](http://localhost:8501). Start on **Data Spot Check** to confirm the marts are populated, then the **Executive Dashboard**. The **BI Assistant** and **AI CFO** pages need an LLM key; the CFO page additionally needs a report to exist, which the Airflow task generates.

## Shutting down

```powershell
docker compose -f infra/docker-compose.yml down
```

Data persists in Docker volumes, so the next `up -d` picks up where you left off.

## More detail

[`docs/runbook.md`](runbook.md) has the full operational reference: first-time setup, rebuilding the Airflow image after changing the DAG or Dockerfile, selective model runs, MetricFlow examples and troubleshooting.
