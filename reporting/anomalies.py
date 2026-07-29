"""Anomaly + risk detection for the AI CFO report (Python, not the LLM).

Two kinds of signal:
  * Statistical outliers: daily points whose value is >= ``z_threshold`` standard
    deviations from the trailing-window mean (same idea as the BI Assistant's
    anomaly scan).
  * Rule flags: simple business rules (e.g. a sharp week-over-week rise in the
    withdrawal ratio) that are worth surfacing even when not statistical outliers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd


@dataclass
class Anomaly:
    metric: str
    label: str
    when: str  # ISO date
    value: float
    z_score: float
    direction: str  # "high" | "low"


@dataclass
class RuleFlag:
    label: str
    detail: str
    severity: str  # "info" | "watch" | "risk"


def zscore_outliers(
    daily: pd.DataFrame,
    value_col: str,
    label: str,
    as_of: date,
    window_days: int = 30,
    z_threshold: float = 2.0,
) -> list[Anomaly]:
    """Flag daily points >= ``z_threshold`` std devs from the window mean."""
    work = daily.copy()
    work["_d"] = pd.to_datetime(work["effective_date"]).dt.date
    window_start = as_of - timedelta(days=window_days - 1)
    win = work[(work["_d"] >= window_start) & (work["_d"] <= as_of)].sort_values("_d")
    vals = pd.to_numeric(win[value_col], errors="coerce")
    series = vals.dropna()
    if len(series) < 4:
        return []
    mean, std = series.mean(), series.std()
    if not std or pd.isna(std):
        return []

    out: list[Anomaly] = []
    for d_val, v in zip(win["_d"], vals):
        if pd.isna(v):
            continue
        z = (v - mean) / std
        if abs(z) >= z_threshold:
            out.append(
                Anomaly(
                    metric=value_col,
                    label=label,
                    when=str(d_val),
                    value=float(v),
                    z_score=round(float(z), 2),
                    direction="high" if z > 0 else "low",
                )
            )
    return out


def _pooled_ratio(work: pd.DataFrame, start: date, end: date) -> float:
    """Σ withdrawals / Σ deposits over [start, end] (pooled, not mean of daily
    ratios) so a multi-day window aggregates the ratio correctly."""
    mask = (work["_d"] >= start) & (work["_d"] <= end)
    num = pd.to_numeric(work.loc[mask, "withdrawals_usd"], errors="coerce").sum()
    den = pd.to_numeric(work.loc[mask, "gross_deposits_usd"], errors="coerce").sum()
    return (num / den) if den else float("nan")


def withdrawal_ratio_rule(
    daily: pd.DataFrame,
    as_of: date,
    rise_threshold_pts: float = 2.0,
) -> RuleFlag | None:
    """Flag a rolling 7d-vs-prior-7d rise in the withdrawal ratio."""
    if not {"withdrawals_usd", "gross_deposits_usd"}.issubset(daily.columns):
        return None
    work = daily.copy()
    work["_d"] = pd.to_datetime(work["effective_date"]).dt.date

    cur_start = as_of - timedelta(days=6)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)

    cur = _pooled_ratio(work, cur_start, as_of)
    prev = _pooled_ratio(work, prev_start, prev_end)
    if pd.isna(cur) or pd.isna(prev):
        return None

    rise_pts = (cur - prev) * 100
    if rise_pts < rise_threshold_pts:
        return None
    return RuleFlag(
        label="Rising withdrawal ratio",
        detail=(
            f"Up {rise_pts:.1f} points week-over-week "
            f"({prev * 100:.1f}% to {cur * 100:.1f}%)"
        ),
        severity="watch",
    )
