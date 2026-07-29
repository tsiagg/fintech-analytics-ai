"""MetricFlow query runner for the BI Assistant.

The assistant is **not** allowed to write SQL. It may only request metrics and
dimensions from the semantic-layer allowlist (see ``semantic.py``); this module
validates that request and hands it to the MetricFlow CLI (``mf query``), which
compiles and runs the SQL against Postgres. We read MetricFlow's CSV output back
into a DataFrame.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

from services.db import postgres_dsn_parts
from services.semantic import get_catalog

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DBT_DIR = _REPO_ROOT / "dbt"
_MF_TIMEOUT_SECONDS = 90


class MetricQueryError(Exception):
    """Raised when a metric request is invalid or MetricFlow fails."""


@dataclass
class MetricQuery:
    metrics: list[str]
    group_by: list[str] = field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    order: list[str] = field(default_factory=list)
    limit: int | None = None
    where: list[str] = field(default_factory=list)  # MetricFlow filter expressions
    filter_summary: list[str] = field(default_factory=list)  # human-readable

    def describe(self) -> dict:
        return {
            "metrics": self.metrics,
            "group_by": self.group_by,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "order": self.order or None,
            "limit": self.limit,
            "filters": self.filter_summary or None,
        }


def _mf_executable() -> str:
    """Locate the ``mf`` console script next to the active interpreter."""
    scripts_dir = Path(sys.executable).parent
    for candidate in ("mf.exe", "mf"):
        path = scripts_dir / candidate
        if path.exists():
            return str(path)
    return "mf"  # fall back to PATH


def _mf_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    # Mirror Postgres connection so MetricFlow/dbt resolve the same warehouse.
    parts = postgres_dsn_parts()
    env.setdefault("POSTGRES_HOST", str(parts["host"]))
    env.setdefault("POSTGRES_PORT", str(parts["port"]))
    env.setdefault("POSTGRES_DB", str(parts["dbname"]))
    env.setdefault("POSTGRES_USER", str(parts["user"]))
    env.setdefault("POSTGRES_PASSWORD", str(parts["password"]))
    return env


def validate_query(query: MetricQuery) -> None:
    """Reject anything outside the semantic-layer allowlist."""
    catalog = get_catalog()
    if not query.metrics:
        raise MetricQueryError("No metric was requested.")

    unknown = [m for m in query.metrics if m not in catalog.metric_names]
    if unknown:
        raise MetricQueryError(f"Unknown metric(s): {', '.join(unknown)}")

    allowed_group_bys = catalog.group_bys_for(query.metrics)
    for gb in query.group_by:
        base = gb.split("__")[0]
        if base == "metric_time":
            grain = gb.split("__")[1] if "__" in gb else "day"
            valid_time = {g for m in query.metrics for g in catalog.metrics[m].time_grains}
            if grain not in valid_time:
                raise MetricQueryError(
                    f"Time grain '{grain}' is not available for {query.metrics}. "
                    f"Allowed: {sorted(valid_time)}"
                )
            continue
        if gb not in allowed_group_bys:
            raise MetricQueryError(
                f"Dimension '{gb}' is not allowed for {query.metrics}. "
                f"Allowed: {sorted(allowed_group_bys) or '(none)'}"
            )


_SAFE_OPERATORS = {"=", "!=", ">", "<", ">=", "<=", "in"}


def _quote(value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    # categorical/text: single-quote and escape embedded quotes
    return "'" + str(value).replace("'", "''") + "'"


def build_filters(metrics: list[str], filters: list[dict]) -> tuple[list[str], list[str]]:
    """Turn structured {dimension, operator, value} filters into validated
    MetricFlow --where clauses. The LLM never writes raw SQL; the app builds the
    expression from an allowlisted dimension + a whitelisted operator.
    """
    catalog = get_catalog()
    allowed = catalog.group_bys_for(metrics)
    where: list[str] = []
    summary: list[str] = []

    for f in filters or []:
        dim = f.get("dimension")
        op = (f.get("operator") or "=").lower()
        value = f.get("value")
        if not dim or dim.startswith("metric_time"):
            raise MetricQueryError(
                "Filters must target a categorical dimension (use the date range "
                "for time)."
            )
        if dim not in allowed:
            raise MetricQueryError(
                f"Filter dimension '{dim}' is not allowed for {metrics}. "
                f"Allowed: {sorted(allowed) or '(none)'}"
            )
        if op not in _SAFE_OPERATORS:
            raise MetricQueryError(f"Unsupported filter operator '{op}'.")

        dim_ref = f"{{{{ Dimension('{dim}') }}}}"
        if op == "in":
            values = value if isinstance(value, list) else [value]
            rendered = ", ".join(_quote(v) for v in values)
            where.append(f"{dim_ref} IN ({rendered})")
            summary.append(f"{dim} in [{', '.join(str(v) for v in values)}]")
        else:
            where.append(f"{dim_ref} {op} {_quote(value)}")
            summary.append(f"{dim} {op} {value}")
    return where, summary


def _coerce_numeric(df: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    for col in df.columns:
        if any(tok in col for tok in ("__day", "__week", "__month", "__quarter", "__year")):
            df[col] = pd.to_datetime(df[col], errors="coerce")
        elif col in metric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _run_mf_cached(
    metrics: tuple[str, ...],
    group_by: tuple[str, ...],
    start_time: str | None,
    end_time: str | None,
    order: tuple[str, ...],
    limit: int | None,
    where: tuple[str, ...] = (),
) -> pd.DataFrame:
    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "mf_out.csv"
        cmd = [
            _mf_executable(),
            "query",
            "--metrics",
            ",".join(metrics),
            "--csv",
            str(out_csv),
            "--quiet",
        ]
        if group_by:
            cmd += ["--group-by", ",".join(group_by)]
        if start_time:
            cmd += ["--start-time", start_time]
        if end_time:
            cmd += ["--end-time", end_time]
        if order:
            cmd += ["--order", ",".join(order)]
        if limit:
            cmd += ["--limit", str(limit)]
        for clause in where:
            cmd += ["--where", clause]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_DBT_DIR),
                env=_mf_env(),
                capture_output=True,
                text=True,
                timeout=_MF_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise MetricQueryError("MetricFlow query timed out.") from exc
        except FileNotFoundError as exc:
            raise MetricQueryError(
                "Could not find the 'mf' CLI. Install app/requirements.txt in the venv."
            ) from exc

        if proc.returncode != 0 or not out_csv.exists():
            detail = (proc.stderr or proc.stdout or "").strip()[-600:]
            raise MetricQueryError(f"MetricFlow query failed.\n{detail}")

        df = pd.read_csv(out_csv)

    metric_cols = [c for c in df.columns if c in metrics]
    return _coerce_numeric(df, metric_cols)


def run_metric_query(query: MetricQuery) -> pd.DataFrame:
    """Validate then execute a metric request via MetricFlow."""
    validate_query(query)
    return _run_mf_cached(
        tuple(query.metrics),
        tuple(query.group_by),
        query.start_time,
        query.end_time,
        tuple(query.order),
        query.limit,
        tuple(query.where),
    )


@st.cache_data(ttl=300, show_spinner=False)
def get_data_date_range() -> tuple[str | None, str | None]:
    """Min/max effective_date in the company KPI mart (for relative ranges)."""
    import psycopg2

    query = (
        "SELECT MIN(effective_date)::text, MAX(effective_date)::text "
        "FROM analytics_dev.mrt_company_daily_kpi"
    )
    try:
        with psycopg2.connect(**postgres_dsn_parts()) as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                row = cur.fetchone()
        return (row[0], row[1]) if row else (None, None)
    except Exception:
        return (None, None)
