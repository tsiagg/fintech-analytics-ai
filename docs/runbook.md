---
title: Appendix - Runbook
nav_order: 11
---

# Runbook (Windows)

Daily commands for this repo. Run PowerShell from the **project root** (folder that contains `infra/`, `dbt/`, `simulation/`).

**Prerequisites:** Docker Desktop installed. Stack = **fintech Postgres** + **Airflow 3** (DAG `daily_fintech_analytics`: simulation → dbt run → dbt test).

---

## Start of day

Do this when you sit down to work (or leave the PC on and want the pipeline running).

1. **Open Docker Desktop** and wait until it shows **Running**.
2. Start the stack (Postgres + Airflow):

```powershell
docker compose -f infra/docker-compose.yml up -d
```

3. **Optional — confirm containers are up:**

```powershell
docker compose -f infra/docker-compose.yml ps
```

4. **Optional — open Airflow UI:** http://localhost:8080 (`airflow` / `airflow`).  
   DAG **daily_fintech_analytics** should be **On**. The scheduler runs automatically; missed days backfill one at a time (`catchup=True`).

You do **not** need to activate `.venv` or trigger the DAG for normal daily operation — Airflow handles simulation and dbt inside Docker.

---

## End of day

Do this before shutting down the PC (or when you want Docker off).

1. Stop containers — **data is kept** in Docker volumes:

```powershell
docker compose -f infra/docker-compose.yml down
```

2. **Optional:** quit **Docker Desktop** if you want Docker fully off.
3. Shut down Windows as usual.

**Next morning:** repeat **Start of day** (Docker Desktop → `up -d`).

---

## First-time setup (once)

### Docker + Airflow

1. Copy env file:

```powershell
Copy-Item .env.example .env
```

2. Build and start:

```powershell
docker compose -f infra/docker-compose.yml build
docker compose -f infra/docker-compose.yml up -d
```

3. Wait until `airflow-init` shows **Exited (0)** in `docker compose ... ps`.
4. Open http://localhost:8080 and confirm DAG **daily_fintech_analytics** appears.

### Python venv (manual sim / dbt on the host — optional)

Only needed if you run simulation or dbt **outside** Airflow (development).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r simulation/requirements.txt
pip install -r dbt/requirements.txt
dbt deps --project-dir dbt --profiles-dir dbt
Copy-Item dbt\profiles.example.yml dbt\profiles.yml
```

If activation fails:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

## Quick checks

### Containers running

```powershell
docker ps --filter name=fintech-postgres
docker ps --filter name=airflow
```

### Latest data dates (after a green DAG run)

```powershell
docker exec -it fintech-postgres psql -U fintech -d fintech -c "SELECT MAX(batch_date) FROM trades;"
docker exec -it fintech-postgres psql -U fintech -d fintech -c "SELECT MAX(effective_date) FROM analytics_dev.mrt_company_daily_kpi;"
```

### List tables

```powershell
docker exec -it fintech-postgres psql -U fintech -d fintech -c "\dt"
```

---

## Airflow

**Config:** `infra/airflow/` · **DAG:** `daily_fintech_analytics`  
**Schedule:** `@daily` from **2026-05-29** · **catchup:** on · **max_active_runs:** 1

### Manual trigger (testing)

1. http://localhost:8080 → DAG **daily_fintech_analytics** → **Trigger DAG**.
2. Open each task → **Log** for simulation JSON, dbt run, and dbt test output.

### Rebuild after changing DAG or Dockerfile

```powershell
docker compose -f infra/docker-compose.yml build airflow-apiserver airflow-scheduler airflow-dag-processor
docker compose -f infra/docker-compose.yml up -d
```

### Troubleshooting

| Issue | What to check |
|-------|----------------|
| DAG not visible | `docker logs airflow-dag-processor` · `infra/airflow/dags/daily_fintech_analytics.py` |
| Simulation fails | Task log · fintech Postgres healthy |
| dbt connection fails | `infra/airflow/dbt/profiles.yml` · `.env` credentials |
| Port 8080 in use | Set `AIRFLOW_WEBSERVER_PORT` in `.env` |
| Log permission errors | Set `AIRFLOW_UID=50000` in `.env` |

---

## Manual simulation (host — optional)

Use when developing the simulator without Airflow. Postgres must be up; activate `.venv` first.

```powershell
.\.venv\Scripts\Activate.ps1
python -m simulation --date 2026-05-17
```

Re-running the **same date** replaces that day (idempotent). Load multiple days **in order**:

```powershell
python -m simulation --date 2026-05-15
python -m simulation --date 2026-05-16
python -m simulation --date 2026-05-17
```

Optional flags:

```powershell
python -m simulation --date 2026-05-17 --scenario market_crash
python -m simulation --list-scenarios
```

---

## Manual dbt (host — optional)

Use when developing models without Airflow. Activate `.venv`; project in `dbt/`, schema **`analytics_dev`**.

```powershell
.\.venv\Scripts\Activate.ps1
dbt debug --project-dir dbt --profiles-dir dbt
dbt run --project-dir dbt --profiles-dir dbt
dbt test --project-dir dbt --profiles-dir dbt
```

After changing `packages.yml`:

```powershell
dbt deps --project-dir dbt --profiles-dir dbt
```

Docs locally:

```powershell
dbt docs generate --project-dir dbt --profiles-dir dbt
dbt docs serve --project-dir dbt --profiles-dir dbt
```

Without activating venv:

```powershell
.\.venv\Scripts\dbt.exe run --project-dir dbt --profiles-dir dbt
```

---

## MetricFlow (host — optional)

From `dbt/` with venv active. **57** metrics in `models/semantic_models/metrics.yml`.

```powershell
cd dbt
dbt parse --profiles-dir .
mf list metrics
```

If `mf` errors on emoji output:

```powershell
$env:PYTHONIOENCODING='utf-8'
mf query --metrics daily_gross_trade_revenue_total --group-by metric_time__day
```

---

## Danger zone — wipes all Postgres data

Only when you **intentionally** want a blank database:

```powershell
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d
```

`-v` removes volumes → **all fintech and Airflow metadata on this stack is gone**.

---

## Streamlit app (Phase 4 — host)

Local AI analytics app (`app/`). Entry point `app/main.py`; multipage app in `app/pages/`. Reads `analytics_dev` marts only — **not** raw `public.*`. Postgres must be up (Docker). No LLM/API key needed for dashboard pages; OpenRouter is only required later for BI Assistant + AI CFO.

**Pages (sidebar):**

| Page | File | Needs API key |
|------|------|---------------|
| Data Spot Check | `0_Data_Spot_Check.py` | No |
| Executive Dashboard | `1_Executive_Dashboard.py` | No |
| BI Assistant | `2_BI_Assistant.py` | Yes — OpenRouter |
| AI CFO | `3_AI_CFO.py` | Yes (not built yet) |

**Serving marts for dashboard:** `mrt_company_daily_kpi`, `mrt_geo_daily_revenue`. After model changes:

```powershell
cd dbt
dbt run --select mrt_company_daily_kpi mrt_geo_daily_revenue
```

### First-time setup (once)

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r app/requirements.txt
```

### Start Streamlit

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/main.py --server.port 8501
```

Then open **http://localhost:8501**. Add `--server.headless true` to stop it auto-opening a browser tab. Streamlit auto-reloads on file save (use **Rerun** / **Always rerun** in the top-right menu).

### Stop Streamlit

Press **Ctrl+C** in the terminal running the server. If it was started in the background, stop it by port:

```powershell
Get-NetTCPConnection -LocalPort 8501 | Select-Object -Expand OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

### Notes

- Port 8501 in use → pick another, e.g. `--server.port 8502`.
- Reads marts from `analytics_dev`; if KPIs look stale, confirm a green DAG run (see **Quick checks**).

---

## BI Assistant (Phase 4 — OpenRouter)

Reactive chat over governed MetricFlow metrics. The assistant plans a metric
request (metric + dimensions + time range), MetricFlow compiles and runs it, then
the LLM explains the numbers. It never writes ad-hoc SQL.

**Config (`.env`):**

```env
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-...
LLM_MODEL_BI_FLASH=deepseek/deepseek-v4-flash   # default (cheap/fast)
LLM_MODEL_BI_PRO=deepseek/deepseek-v4-pro       # root-cause / compare / anomaly
LLM_MODEL_CFO=google/gemini-3.1-pro-preview     # AI CFO (later)
```

**Model routing:** Flash by default; auto-escalates to Pro for questions with
words like *why / root cause / compare / anomaly / driver*, or if Flash fails.
Each answer shows the model used and token count.

**Cost control:** set a **~$15/month spend limit** on the OpenRouter key. Prompts
send compact metric JSON, not full tables; `max_tokens` is capped per call.

**Requires:** Postgres up (marts in `analytics_dev`) and the `mf` CLI in the venv
(`pip install -r app/requirements.txt`). MetricFlow runs from the `dbt/` project.

**Try it:** open the page → click an example prompt (e.g. *"How was the revenue
last 7 days?"*) or type a question. The catalog prompt (*"What metrics and
dimensions can you report on?"*) answers locally with no LLM call.

## Later

Add the **AI CFO** OpenRouter workflow (`cfo_engine.py`, `LLM_MODEL_CFO`) and the
Phase 5 full-stack compose here as the project grows.
