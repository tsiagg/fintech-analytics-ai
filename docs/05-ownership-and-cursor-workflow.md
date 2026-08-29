---
title: How this project was built
parent: About this project
nav_order: 2
---

# How this project was built

This page is about **this repository**, not employment history. Roles and employers are on the [CV]({{ '/cv/' | relative_url }}). What follows is who wrote which layer here, and how I reviewed the AI-generated parts.

This project was built with an AI coding agent. Pretending otherwise would be both dishonest and a wasted opportunity, because how you direct and verify an agent is now part of the job.

## Who owns what

I set this out in [`docs/learning-and-ownership.md`](learning-and-ownership.md) **before writing the code**, not afterwards as a rationalisation. The file is in the repo with its original dates.

The reasoning behind the split is that I am training as an analytics engineer, so the value I need to own is modelling, metric definition and the trust layer. A user interface is a way to demonstrate that work, not the work itself.

- **`simulation/` and the raw schema** — agent built. This represents the data engineering team and the upstream product. An analytics engineer does not create or move source data.
- **dbt staging, intermediate, marts** — mine, deeply. Grain decisions, the split of facts by process, the business logic in trading economics.
- **MetricFlow semantic layer** — mine, deeply. Every metric definition, and the argument for why each one is defined the way it is.
- **Airflow DAG** — mostly agent. I own the design decisions: sequential backfill, `dbt_test` as a separate gate before the report.
- **Streamlit app** — agent built. I chose which visuals answer which question and wrote the SQL behind them; the agent turned that into working pages.
- **BI Assistant and CFO reporting engine** — collaborative. I set the guardrail design and report structure; the agent implemented the application plumbing after explaining the pattern to me.

## How the repo is scaffolded for agents

The single most useful thing I did was accept that **the agent is stateless and the repository is not.** Anything the agent needs to know has to live in files, or it gets re-litigated every session.

That produced three artifacts, all in [`model-implementation-planning/`](https://github.com/tsiagg/fintech-analytics-ai/tree/main/model-implementation-planning):

**A brief per phase.** Each phase folder holds a README with goals, deliverables, expected tools, and — the part that does the real work — an **explicit out-of-scope list**. Phase 5's brief says no new marts and no production hardening. Without that line, an agent asked to "polish the project" will happily build three more features.

**A roadmap as living state.** [`ROADMAP.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/ROADMAP.md) holds progress bars, a Gantt chart and per-phase checklists, updated when something ships. It is how a new session finds out what is done, what was deferred and why. Items marked deferred — the affiliate mart, the regional daily KPI mart — stay visible as decisions rather than vanishing.

**A backlog that absorbs ideas.** [`IMPROVEMENTS.md`](https://github.com/tsiagg/fintech-analytics-ai/blob/main/model-implementation-planning/IMPROVEMENTS.md) exists so that a good idea mid-phase becomes a row in a table instead of scope creep. Eleven items are logged there, each with effort and priority, several referenced from these docs as known gaps.

The pattern generalises: **write the constraints down, keep state in the repo, and let the backlog absorb everything that is not this phase.** It is the same discipline that makes a data team work, applied to working with a machine.

## Where AI wrote and I reviewed

Stated plainly, because the code is public and anyone can tell:

- **`simulation/`** — effectively all agent. By design.
- **Streamlit pages and components** — agent, to my direction on layout and chart choice.
- **The large Python modules** — agent-written to an architecture I specified. `bi_engine.py` is around 480 lines and `reporting/inputs.py` around 580. I could not have written those quickly from scratch. I could specify what had to be true about them, trace their output and identify when they were wrong.
- **The CFO HTML template** — agent.
- **Airflow boilerplate** — agent; the scheduling semantics were my call.
- **dbt models, tests and metric YAML** — mine. This is the part I would sit and defend.
- **This documentation** — drafted by an agent reading the codebase, then reviewed and corrected by me. The structure, the emphasis, and the decision about which limitations to disclose are mine.

## How I QA an agent

This is the skill that made the rest possible, and it is mostly not about prompting.

**Make it teach before it builds.** For the BI Assistant I asked for the retrieval and guardrail pattern to be explained step by step, with a pause for my decision at each one, before any code was written. If I cannot explain why a guardrail exists, I cannot review the code that implements it, and I have just accepted a black box into my own project.

**Write the test with the model, not after it.** Every mart states its grain in YAML and has a `unique_combination_of_columns` test asserting it. An agent will produce SQL that looks correct and fans out on a join. The test is what makes that a red pipeline instead of a plausible number.

**Smoke-test the semantic layer separately.** Metrics were validated with `dbt parse` and direct `mf query` runs before any of them were wired into the app, so that a wrong number could only be a metric problem or an app problem, never ambiguously both.

**Build the reconciliation tool early.** The Data Spot Check page exists so that "the dashboard looks wrong" resolves in seconds into "the mart is wrong" or "the app is wrong". It is the cheapest debugging investment in the project.

**Keep a defined trace for disagreement.** When a KPI looks off, the path is fixed: Streamlit, then the serving mart, then the core mart, then intermediate, then raw. Because the layers are thin and each has one job, the wrong step is usually obvious within a few minutes.

**Do not ship a system I cannot explain.** The ownership split in [`learning-and-ownership.md`](learning-and-ownership.md) was written before the code. If a layer is marked mine, I can defend it. If it is marked designed-and-reviewed, I can say what had to be true and how I checked. Working with an agent makes it easy to end up with a working system you cannot explain; that file is the check against it.

## The honest summary

An agent let me build a stack that would otherwise have taken months, and it removed exactly none of the need to understand the modelling layer. Where I could not have written the code, I could still specify it, test it, and recognise wrong output — and where the code is genuinely mine, it is the part a data team would care about most.
