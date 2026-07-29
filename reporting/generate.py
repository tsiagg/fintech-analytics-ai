"""Generate and store the AI CFO report for a given date.

Run from the repo root (Airflow sets PYTHONPATH=/opt/fintech):

    python -m reporting.generate --date 2026-06-20

If ``--date`` is omitted, today is used. The date is clamped to the latest day
available in ``mrt_company_daily_kpi`` so a scheduled run never asks for a day
the warehouse has not loaded yet.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from reporting import data as data_mod
from reporting import store
from reporting.engine import generate_report
from reporting.inputs import build_inputs

_REPO_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)


def _load_env() -> None:
    """Best-effort .env load for local runs (Airflow injects env directly)."""
    try:
        from dotenv import dotenv_values, load_dotenv

        env_path = _REPO_ROOT / ".env"
        load_dotenv(env_path)
        # Compose may inject LLM_API_KEY="" when repo-root .env is not used for
        # substitution; default load_dotenv will not replace an existing empty var.
        if not os.environ.get("LLM_API_KEY", "").strip():
            for key, val in dotenv_values(env_path).items():
                if key.startswith("LLM_") and (val or "").strip():
                    os.environ[key] = val.strip()
    except Exception:
        pass


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )


def run(as_of: date) -> int:
    logger.info("Starting CFO report generation for as_of=%s", as_of)

    logger.info("Loading warehouse marts from Postgres (analytics_dev schema)")
    daily = data_mod.load_company_daily_kpi()
    monthly = data_mod.load_monthly_performance()
    instrument = data_mod.load_instrument_daily_kpi()
    logger.info(
        "Loaded mrt_company_daily_kpi: %s rows; mrt_company_monthly_performance: %s rows; "
        "mrt_instrument_daily_kpi: %s rows",
        len(daily),
        len(monthly),
        len(instrument),
    )
    if daily.empty:
        raise SystemExit("mrt_company_daily_kpi is empty - run dbt before generating the report.")

    latest = pd.to_datetime(daily["effective_date"]).max().date()
    if as_of > latest:
        logger.warning("Requested %s is beyond loaded data; clamping to latest %s", as_of, latest)
        as_of = latest

    data_range = data_mod.get_data_date_range()
    logger.info("Warehouse date range: %s -> %s", data_range[0], data_range[1])

    logger.info("Building report inputs (scorecard, targets, anomalies, forecast)")
    ctx = build_inputs(daily, monthly, as_of, data_range, instrument=instrument)
    logger.info(
        "Inputs ready: %s scorecard metrics, %s target rows, %s regions, %s anomaly flags",
        len(ctx.get("scorecard", [])),
        len(ctx.get("targets", [])),
        len(ctx.get("regional", [])),
        len(ctx.get("anomalies", {}).get("rules", []))
        + len(ctx.get("anomalies", {}).get("outliers", [])),
    )

    logger.info("Generating narrative and rendering HTML template")
    result = generate_report(ctx)

    logger.info(
        "Persisting report to %s (report_date=%s, html_bytes=%s)",
        store.TABLE,
        as_of,
        len(result.report_html.encode("utf-8")),
    )
    new_id = store.save_report(
        report_date=as_of,
        period_start=as_of.replace(day=1),
        period_end=as_of,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        inputs=ctx,
        narrative=result.narrative,
        report_html=result.report_html,
    )
    logger.info(
        "Saved CFO report id=%s for %s (model=%s, tokens=%s)",
        new_id,
        as_of,
        result.model,
        result.total_tokens,
    )
    return new_id


def main() -> None:
    _load_env()
    _configure_logging()
    parser = argparse.ArgumentParser(description="Generate the AI CFO report.")
    parser.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD")
    args = parser.parse_args()
    run(_parse_date(args.date))


if __name__ == "__main__":
    main()
