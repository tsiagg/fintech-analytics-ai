# Screenshot capture guide

Internal note. Excluded from the published site.

Six slots are prepared. Each one already has a commented-out image line sitting in the right place in the docs, so the workflow is:

1. Capture the shot.
2. Save it in this folder using the **exact filename** below.
3. Uncomment the matching line in the file listed. Search for the filename to find it.

Nothing is referenced until you uncomment, so the site stays clean with zero screenshots, six, or any number in between.

## General rules

- **Light mode**, both in the browser and in Streamlit. The docs site is light; dark screenshots look like holes in the page.
- **Window about 1400 px wide.** Wider and the text is unreadable when the image is scaled down into the page.
- **Crop to the content.** No browser chrome, no bookmarks bar, no taskbar, no desktop.
- **Check for anything personal** before saving: other tabs, your name in the OS bar, local file paths.
- **PNG**, and keep each file under roughly 400 KB.
- Capture **after a decent backfill** — three or four weeks minimum — or the charts look empty and the comparisons show nothing.

## The six shots

### 1. `executive-dashboard.png`
**Goes in:** `docs/01-what-i-built.md`, under "Executive dashboard"

The four KPI cards with their sparklines, plus the weekly stacked revenue bar below. Pick a date range where the numbers actually move, and if you can, one where a comparison badge is negative — a dashboard that only ever shows green looks fake. Make sure the region/country toggle is visible.

### 2. `bi-assistant.png`
**Goes in:** `docs/01-what-i-built.md`, under "BI Assistant"

The single most important shot, so spend the most time here. Show one complete answer: the question, the chart, the data table and the written explanation, **with the model and token badge visible**. Ask a "why" or "compare" question so it escalates to the Pro tier and the badge proves the routing is real. A question that produces a breakdown by region or user group demonstrates far more than a single-number answer.

### 3. `ai-cfo-report.png`
**Goes in:** `docs/01-what-i-built.md`, under "AI CFO report"

The top of the report: the masthead, the scorecard tiles, and enough of the first two sections to show that the prose sits alongside real tables. If the whole report will not fit legibly, capture the executive summary plus the trends-against-target section rather than zooming out until nothing is readable.

### 4. `airflow-dag.png`
**Goes in:** `docs/01-what-i-built.md`, under "The daily pipeline"

Graph view of `daily_fintech_analytics` with all four tasks green. If the grid of recent runs can be included in the same frame, do it — a column of successful days says more about the pipeline than one green run does.

### 5. `dbt-lineage.png`
**Goes in:** `docs/02-architecture-and-data-model.md`, under "Why the layers are split this way"

The best shot for an analytics audience. Run `dbt docs generate` then `dbt docs serve`, open `mrt_company_daily_kpi`, and capture the full lineage graph so the raw → staging → intermediate → mart → serving chain is visible in one image. This is the picture that proves the layering claim in the text.

### 6. `data-spot-check.png` (optional)
**Goes in:** `docs/01-what-i-built.md`, under "Data spot check"

Lowest priority. A mart table with the date filter and the CSV export button visible. Only worth including if the other five are done.

## If you want a hero image

`README.md` has a commented-out line near the top for `executive-dashboard.png`. A single screenshot at the top of the repo landing page is the highest-return one, because it is the first thing anyone sees on GitHub. Uncomment it once shot 1 exists.
