"""Month-end projections for the AI CFO report.

Two transparent methods, each returning the projected month-end value AND a
human-readable method name so the report can state how the number was produced:

  * Run-rate average: MTD sum scaled to the full month (days_in_month / days_elapsed).
  * Linear regression (OLS via ``numpy.polyfit``, degree 1) fitted on the current
    month's daily points only, with the remaining days of the month extrapolated
    (each day floored at 0) and added to the MTD actual.

Per the trust model, the LLM never invents these numbers; it only interprets them.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd


@dataclass
class Forecast:
    metric: str
    method: str  # human-readable, shown verbatim in the report
    projected_month_end: float
    actual_so_far: float
    basis_points: int  # number of daily points used


def days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def _mtd_sum(daily: pd.DataFrame, value_col: str, as_of: date) -> tuple[float, int]:
    month_start = as_of.replace(day=1)
    work = daily.copy()
    work["_d"] = pd.to_datetime(work["effective_date"]).dt.date
    mtd = work[(work["_d"] >= month_start) & (work["_d"] <= as_of)]
    total = float(pd.to_numeric(mtd[value_col], errors="coerce").sum())
    return total, len(mtd)


def run_rate_projection(daily: pd.DataFrame, value_col: str, as_of: date) -> Forecast:
    """Linear pro-rata: scale the month-to-date sum to the full month."""
    actual, n_points = _mtd_sum(daily, value_col, as_of)
    month_start = as_of.replace(day=1)
    days_elapsed = max((as_of - month_start).days + 1, 1)
    n_days = days_in_month(as_of)
    projected = actual / days_elapsed * n_days
    return Forecast(
        metric=value_col,
        method=(
            f"Run-rate average (month-to-date sum scaled from {days_elapsed} "
            f"to {n_days} days)"
        ),
        projected_month_end=projected,
        actual_so_far=actual,
        basis_points=n_points,
    )


def linear_regression_projection(
    daily: pd.DataFrame,
    value_col: str,
    as_of: date,
) -> Forecast | None:
    """Fit an OLS line (numpy.polyfit deg=1) on the *current month's* daily
    points and project the remaining days of the month, added to the
    month-to-date actual.

    The fit is scoped to the current month (not a trailing window that bleeds
    into the prior month) so a month boundary cannot inject a spurious slope.
    Each projected day is floored at 0 so a downtrend still contributes a
    sensible (non-negative) amount instead of collapsing the whole remainder to
    zero and silently returning the actual as the "forecast".

    Returns ``None`` when there are too few in-month points to fit a line, in
    which case the caller falls back to the run-rate projection.
    """
    work = daily.copy()
    work["_d"] = pd.to_datetime(work["effective_date"]).dt.date
    month_start = as_of.replace(day=1)
    win = work[(work["_d"] >= month_start) & (work["_d"] <= as_of)].sort_values("_d")
    vals = pd.to_numeric(win[value_col], errors="coerce").dropna()
    if len(vals) < 3:
        return None

    x = np.arange(len(vals), dtype=float)
    y = vals.to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)

    actual, _ = _mtd_sum(daily, value_col, as_of)
    n_days = days_in_month(as_of)
    days_remaining = n_days - ((as_of - month_start).days + 1)

    projected_remaining = 0.0
    for i in range(1, days_remaining + 1):
        # Floor each projected day at 0 so a downward slope tapers off rather
        # than producing (and then clamping away) a large negative remainder.
        projected_remaining += max(intercept + slope * (len(vals) - 1 + i), 0.0)
    projected = actual + projected_remaining

    return Forecast(
        metric=value_col,
        method=(
            f"Linear regression (OLS via numpy.polyfit, degree 1) on the "
            f"{len(vals)} day(s) so far this month; remaining "
            f"{days_remaining} day(s) projected (each floored at 0)"
        ),
        projected_month_end=projected,
        actual_so_far=actual,
        basis_points=len(vals),
    )


def project_month_end(
    daily: pd.DataFrame,
    value_col: str,
    as_of: date,
    prefer: str = "linear_regression",
) -> Forecast:
    """Preferred method with a graceful fallback to run-rate."""
    if prefer == "linear_regression":
        lr = linear_regression_projection(daily, value_col, as_of)
        if lr is not None:
            return lr
    return run_rate_projection(daily, value_col, as_of)
