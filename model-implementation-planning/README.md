# Model implementation planning

Use this folder as the **single planning hub** for the AI-powered fintech analytics portfolio project.

## Source brief

- **`Analytics Project Summary - Fintech Simulation.docx`** — full vision, data model, tools, and phased roadmap. **Kept locally, not published to the repo** (a binary GitHub cannot render). [ROADMAP.md](./ROADMAP.md) carries everything from it that is still current, so the phase briefs' "parent brief" references are local-only.

## Visual progress

**[ROADMAP.md](./ROADMAP.md)** — Gantt charts (Mermaid), progress bars and checklist tables. **Phases 1–4 are complete and the Phase 5 documentation has shipped.** The remaining Phase 5 ideas — screenshots, a sample backfill script and Streamlit in Docker Compose — were reviewed and deliberately left out of scope.

## Future improvements

**[IMPROVEMENTS.md](./IMPROVEMENTS.md)** — a small, living backlog of optional updates and refinements (separate from the committed phased roadmap). Add ideas here as they come up.

## Phases (agent briefs)

| Phase | Folder | Focus | Status |
|-------|--------|--------|--------|
| 1 | [phase-1](./phase-1/) | Synthetic data, scenario engine, PostgreSQL raw layer, manual CLI loads | **Done** |
| 2a | [phase-2](./phase-2/) | dbt staging / intermediate / core marts, seeds, tests | **Done** |
| 2b | [phase-2](./phase-2/#phase-2b--ai-ready-metrics--semantic-layer) | KPI + serving + **57** MetricFlow metrics + `mf query` validated | **Done** |
| 3 | [phase-3](./phase-3/) | **One Airflow DAG:** sim → dbt run → dbt test → `generate_cfo_report` | **Done** |
| 4 | [phase-4](./phase-4/) | **Streamlit:** dashboard + **BI Assistant** + **AI CFO** (OpenRouter) | **Done** |
| 5 | [phase-5](./phase-5/) | Portfolio story and documentation; compose, screenshots and sample backfill reviewed but left out of scope | **Documentation shipped** |

### Architecture flow (target end state)

```text
simulation → Postgres (raw)
    → dbt (marts + MetricFlow semantic metrics)
    → Airflow (daily DAG)
    → Streamlit (dashboard | BI Assistant | AI CFO)
```

**Trust model:** KPIs computed in the warehouse; LLM interprets retrieved facts only. BI Assistant and AI CFO use **separate** prompts and workflows.

### Roadmap notes

- **Airflow** lives in Phase 3 only (not Phase 1).
- **dbt Cloud Semantic Layer** is not required — use **MetricFlow on dbt Core** with Postgres.
- **Pipeline / DAG health UI** is out of scope for Streamlit; show Airflow in Phase 5 **screenshots** and runbook.
- **FastAPI** removed from plan — `app/services/` queries marts directly.

Each phase folder contains a **README.md** with goals, deliverables, tools, and notes for implementation agents.

## Folder contents (quick reference)

```text
model-implementation-planning/
  README.md
  ROADMAP.md          ← Gantt + progress tracker (update when you ship)
  IMPROVEMENTS.md     ← future-updates backlog (ideas / refinements / tech debt)
  Analytics Project Summary ... .docx   ← local only, gitignored
  phase-1/README.md
  phase-2/README.md   ← Phase 2a (core) + Phase 2b (semantic layer)
  phase-3/README.md
  phase-4/README.md
  phase-5/README.md
```

If **Explorer** does not show `phase-1` … `phase-5` under this folder, expand the folder or run **Developer: Reload Window** (`Ctrl+Shift+P`).

*(Folder was renamed from `model implementation planning` to `model-implementation-planning` for simpler paths in tools and git.)*
