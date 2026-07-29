# Phase 5 — Portfolio packaging (storytelling + demos)

**Parent brief:** See `../Analytics Project Summary - Fintech Simulation.docx`.

**Prerequisites:** Phase 4 app runs locally (dashboard required; BI + CFO with API key optional but demo-ready).

## Goal

Package the project as a **recruiter-ready portfolio**: clear narrative, reproducible local setup, and **shareable demo assets** — without adding new product features.

**Light scope:** No Streamlit pipeline page, no new marts, no production hardening. Polish docs and visuals.

## What to build

### Documentation (storytelling)

| Deliverable | Purpose |
|-------------|---------|
| **Root `README.md`** | Problem → architecture → trust model (metrics in warehouse, AI interprets) → phase map → 5-minute demo script |
| **`docs/architecture.md`** *(optional)* | One Mermaid diagram: sim → Postgres → dbt (+ MetricFlow) → Airflow → Streamlit |
| **`.env.example`** | Postgres + `LLM_API_BASE` / `LLM_API_KEY` / model names (optional for demo) |
| **KPI glossary** | Link to `dbt/models/marts/marts.yml` + semantic metrics YAML |
| **Scenario reference** | Summarize `simulation/scenarios.py` for demo narrative (e.g. `market_crash` day) |

**Suggested README narrative arc**

1. Simulated fintech warehouse for portfolio / learning  
2. Analytics engineering: dbt marts + semantic metrics  
3. Orchestration: single Airflow DAG  
4. AI layer: BI Assistant + AI CFO with guardrails  
5. How to run locally in ~10 minutes  

### Docker & reproducibility

| Deliverable | Purpose |
|-------------|---------|
| **`docker compose`** | Postgres + Airflow + Streamlit (document one command from repo root) |
| **Sample data script** | Backfill 30–60 days; include at least one interesting scenario day |
| **Smoke path** | Clone → env → compose up → load sample → open Streamlit (LLM optional) |

Public hosting of Postgres (Streamlit Cloud, etc.) is **optional** — primary shareable artifact is **GitHub + README + screenshots**.

### Demo assets (screenshots — required)

Capture after a successful multi-day backfill:

| Screenshot | Shows |
|------------|--------|
| Executive dashboard | KPI cards + trends |
| BI Assistant | Question, chart, SQL, explanation |
| AI CFO report | Structured sections |
| Airflow DAG | Graph view + green run *(replaces in-app pipeline page)* |
| dbt lineage / docs | Mart layer or semantic metrics |
| MetricFlow / semantic YAML | Optional — analytics engineering depth |

**Optional:** 2–3 minute Loom walkthrough; PDF/Notion case study for LinkedIn.

### Shareable options (pick what fits your time)

| Channel | Effort |
|---------|--------|
| Public GitHub repo | Low — primary |
| README + screenshots in repo `docs/demo/` | Low |
| Short Loom video | Low–medium |
| Notion / PDF case study | Low |
| Streamlit Community Cloud + hosted DB | High — usually skip |

## Outputs / acceptance criteria

- New reviewer can follow README and reach dashboard (and optionally BI/CFO with own API key).
- Repo tells a coherent story across Phases 1–4 without reading every folder.
- No secrets in git; demo data volume reasonable for clone-and-run.
- Orchestration visible via **Airflow screenshot**, not a custom monitoring UI.

## Tools (expected)

Git, GitHub, Docker, Markdown; optional Loom; Plotly/Streamlit for capturing UI.

## Notes for agents

- Link to `model-implementation-planning/ROADMAP.md` from root README.
- Document **~€20/month** OpenRouter budget and that LLM is optional for first-run smoke test.
- Call out simulator limitations (activity retention vs churn) honestly in portfolio copy.
- Do not block Phase 5 on perfect production deploy — local compose + story is enough.

## Explicitly out of scope

- Streamlit pipeline / DAG health page  
- FastAPI service  
- dbt Cloud Semantic Layer subscription  
- Multi-environment CI/CD beyond optional `dbt test` on PR  
