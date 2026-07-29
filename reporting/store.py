"""Persist and fetch AI CFO report runs in Postgres.

One row per generated report in ``analytics_dev.cfo_report_runs``. The Airflow
task writes a row; the Streamlit page reads the most recent one. This is an
app-managed table (not a dbt model), so it self-creates on first write.
"""

from __future__ import annotations

import json
from datetime import date

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from reporting.data import ANALYTICS_SCHEMA, postgres_dsn_parts

TABLE = f"{ANALYTICS_SCHEMA}.cfo_report_runs"

_DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id                BIGSERIAL PRIMARY KEY,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    report_date       DATE NOT NULL,
    period_start      DATE,
    period_end        DATE,
    model             TEXT,
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    inputs_json       JSONB,
    narrative_json    JSONB,
    report_html       TEXT NOT NULL
);
"""


def _json(obj) -> Json:
    # default=str guards against any stray non-JSON-native values (e.g. dates).
    return Json(obj, dumps=lambda o: json.dumps(o, default=str))


def ensure_table() -> None:
    with psycopg2.connect(**postgres_dsn_parts()) as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {ANALYTICS_SCHEMA};")
            cur.execute(_DDL)
        conn.commit()


def save_report(
    *,
    report_date: date,
    period_start: date | None,
    period_end: date | None,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    inputs: dict,
    narrative: dict,
    report_html: str,
) -> int:
    ensure_table()
    with psycopg2.connect(**postgres_dsn_parts()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE} (
                    report_date, period_start, period_end, model,
                    prompt_tokens, completion_tokens,
                    inputs_json, narrative_json, report_html
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    report_date,
                    period_start,
                    period_end,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    _json(inputs),
                    _json(narrative),
                    report_html,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def fetch_latest() -> dict | None:
    """Most recent report, or ``None`` if the table is missing/empty."""
    try:
        with psycopg2.connect(**postgres_dsn_parts()) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"SELECT * FROM {TABLE} ORDER BY generated_at DESC, id DESC LIMIT 1;"
                )
                row = cur.fetchone()
        return dict(row) if row else None
    except psycopg2.Error:
        return None
