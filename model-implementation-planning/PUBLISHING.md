# Publishing to GitHub and GitHub Pages

Internal note, deliberately kept out of the published site. The documentation site lives in `/docs` and is served by GitHub Pages from the `main` branch.

**Repo:** https://github.com/tsiagg/fintech-analytics-ai
**Site:** https://tsiagg.github.io/fintech-analytics-ai/

## One-time repo setup (done)

The repository was created empty on github.com — public, with no README, `.gitignore` or licence, since the project already had its own. Then, from the project root:

```powershell
git init
git config user.name "tsiagg"
git config user.email "<your-commit-email>"
git check-ignore -v .env        # must print a matching rule before staging anything
git add -A
git status --short              # confirm .env is absent
git commit -m "Fintech analytics portfolio: simulation, dbt marts and semantic layer, Airflow DAG, Streamlit AI layer"
git branch -M main
git remote add origin https://github.com/tsiagg/fintech-analytics-ai.git
git push -u origin main
```

The identity is set **per-repository**, not globally. If you want it machine-wide for other projects, rerun the two `git config` lines with `--global`.

**On the commit email.** Whatever address is configured here is embedded in every commit and is publicly readable on GitHub. If you would rather not publish a personal address, enable **Settings → Emails → Keep my email addresses private** on GitHub and use the `ID+username@users.noreply.github.com` address it gives you. Commits already pushed keep the old address unless the history is rewritten, so this is worth deciding early.

## Enabling Pages

Repository **Settings** → **Pages** → Build and deployment → Source **Deploy from a branch** → Branch `main`, folder `/docs` → Save. The site builds in a minute or two.

## How the site is put together

`docs/_config.yml` is the whole configuration. It uses the `just-the-docs` remote theme, which gives a sidebar and search without vendoring a theme into the repo.

Pages are ordered by the `nav_order` in each file's front matter:

1. `index.md` — start here
2. `01-what-i-built.md`
3. `02-architecture-and-data-model.md`
4. `03-semantic-layer-and-metric-trust.md`
5. `04-bi-implementation-strategy.md`
6. `05-ownership-and-cursor-workflow.md`
7. `06-skills.md`
8. `07-file-guide.md`
9. `08-run-it-yourself.md`
10. `learning-and-ownership.md` — appendix
11. `runbook.md` — appendix

`cfo_report_latest.html` is published as-is so the site can link to a real generated report. The two design drafts, `cfo_report_mockup.html` and `cfo_report_rendered_sample.html`, are listed under `exclude` in `_config.yml` and are not built.

## Workflow for documentation changes

Documentation lands through a pull request rather than direct commits to `main`, so the change is reviewable and the site does not update until merge:

```powershell
git checkout -b docs/<topic>
# edit
git add -A
git commit -m "..."
git push -u origin docs/<topic>
```

GitHub prints a compare URL on push; open the pull request from there, review the diff, merge, then locally:

```powershell
git checkout main
git pull
```

## Before any push

- `git check-ignore -v .env` must print a rule. The OpenRouter key lives in `.env`.
- `git status --short` before committing, to catch anything new and unexpected.

## What is deliberately not published

`.gitignore` covers secrets, dependencies and build output: `.env`, `.venv/`, `dbt/profiles.yml`, `dbt/target/`, `dbt/dbt_packages/`, `dbt/logs/`, `logs/`, `terminal_boot.log` and `__pycache__/`. Airflow task logs are handled by `infra/airflow/.gitignore`.

Four things were tracked in the first push and then removed with `git rm --cached`, so they still exist locally but are no longer in the repository:

- **`infra/airflow/config/airflow.cfg`** — 109 KB of generated Airflow defaults, and previously the largest file in the repo. Airflow recreates it on first start, so a fresh clone is unaffected. Tracking generated config makes every version upgrade look like a deliberate change.
- **`model-implementation-planning/*.docx`** — the original project brief. A binary GitHub cannot render; `ROADMAP.md` carries what is still current.
- **`docs/cfo_report_mockup.html`** and **`docs/cfo_report_rendered_sample.html`** — superseded design drafts. `docs/cfo_report_latest.html` is a real generated report and stays, because the site links to it.

Also deleted outright: **`app/components/`**, three modules no page ever imported. Recoverable from commit `25b00cb` if ever needed.

## Known follow-ups

- **Screenshots are not captured.** Slots are prepared: see `docs/assets/screenshots/CAPTURE-GUIDE.md` for what each shot should show and which commented-out line to uncomment.
- `.env.example` still describes the AI CFO as "not built yet". Stale comment, harmless, worth a one-line fix.
- Phase 5 packaging beyond documentation — a Streamlit service in the compose file and a 30-to-60-day backfill script — was scoped and deliberately not done. See `phase-5/README.md`.
