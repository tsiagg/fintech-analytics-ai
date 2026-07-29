"""Assemble the structured inputs for the AI CFO report.

Everything quantitative is computed here (in Python) so the LLM only has to
interpret pre-computed numbers:

  * Rolling 7-day vs prior-7-day week-over-week (WoW) per key metric.
  * Month-to-date (MTD) vs prior month over the same number of days.
  * Pace-adjusted target attainment for the three seed-targeted metrics only
    (active traders, net trade revenue, gross deposits).
  * Regional performance vs target.
  * Statistical anomalies + rule flags.
  * Month-end forecasts (run-rate + linear regression), each with its method.

``build_inputs`` returns a single dict that is both rendered by the Jinja2
template and summarized into a ``facts`` block for the LLM prompt.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from reporting import anomalies as anomalies_mod
from reporting.forecasting import days_in_month, project_month_end

# Status bands confirmed with the user: at-risk 90-100%, off-track <90%.
AT_RISK_FLOOR = 0.90

# Per-metric display config. ``good`` says which direction is favourable, so the
# scorecard can colour a move green/red independently of its numeric sign.
METRICS: dict[str, dict] = {
    "net_revenue_usd": {"label": "Net Revenue", "agg": "sum", "fmt": "usd", "good": "up"},
    "gross_revenue_usd": {"label": "Gross Revenue", "agg": "sum", "fmt": "usd", "good": "up"},
    "active_users": {"label": "Active Traders", "agg": "mean", "fmt": "int", "good": "up"},
    "gross_deposits_usd": {"label": "Gross Deposits", "agg": "sum", "fmt": "usd", "good": "up"},
    "withdrawals_usd": {"label": "Withdrawals", "agg": "sum", "fmt": "usd", "good": "down"},
    "net_flow_usd": {"label": "Net Flow", "agg": "sum", "fmt": "usd", "good": "up"},
    "withdrawal_ratio": {"label": "Withdrawal Ratio", "agg": "mean", "fmt": "ratio", "good": "down"},
    "net_revenue_per_user_usd": {"label": "Net Revenue / User", "agg": "mean", "fmt": "usd2", "good": "up"},
    "gross_deposit_per_user_usd": {"label": "Gross Deposit / User", "agg": "mean", "fmt": "usd2", "good": "up"},
    "new_users": {"label": "New Users", "agg": "sum", "fmt": "int", "good": "up"},
}

# The three (and only three) metrics with plan targets in region_monthly_targets.
TARGET_METRICS = [
    {
        "key": "net_trade_revenue",
        "label": "Net trade revenue",
        "actual_col": "actual_net_trade_revenue_usd",
        "target_col": "target_net_trade_revenue_usd",
        "fmt": "usd",
    },
    {
        "key": "active_traders",
        "label": "Active traders",
        "actual_col": "actual_active_users",
        "target_col": "target_active_users",
        "fmt": "int",
    },
    {
        "key": "gross_deposits",
        "label": "Gross deposits",
        "actual_col": "actual_gross_deposit_usd",
        "target_col": "target_gross_deposit_usd",
        "fmt": "usd",
    },
]


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _is_na(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


def fmt_usd(v, signed: bool = False) -> str:
    if _is_na(v):
        return "n/a"
    sign = "-" if v < 0 else ("+" if (signed and v > 0) else "")
    a = abs(float(v))
    if a >= 1_000_000:
        body = f"${a / 1_000_000:.2f}M"
    elif a >= 1_000:
        body = f"${a / 1_000:.0f}k"
    else:
        body = f"${a:,.0f}"
    return sign + body


def fmt_usd2(v) -> str:
    return "n/a" if _is_na(v) else f"${float(v):,.2f}"


def fmt_int(v) -> str:
    return "n/a" if _is_na(v) else f"{float(v):,.0f}"


def fmt_ratio_pct(v) -> str:
    """A 0..1 ratio rendered as a percent."""
    return "n/a" if _is_na(v) else f"{float(v) * 100:.1f}%"


def _fmt_value(v, fmt: str) -> str:
    return {
        "usd": fmt_usd,
        "usd2": fmt_usd2,
        "int": fmt_int,
        "ratio": fmt_ratio_pct,
    }.get(fmt, fmt_int)(v)


def fmt_signed_pct(pct) -> str:
    return "n/a" if _is_na(pct) else f"{pct:+.1f}%"


# --------------------------------------------------------------------------- #
# Window math
# --------------------------------------------------------------------------- #
def _with_date(daily: pd.DataFrame) -> pd.DataFrame:
    work = daily.copy()
    work["_d"] = pd.to_datetime(work["effective_date"]).dt.date
    return work


def _agg(series: pd.Series, how: str) -> float:
    s = pd.to_numeric(series, errors="coerce")
    return float(s.sum()) if how == "sum" else float(s.mean())


def _range_value(work: pd.DataFrame, col: str, start: date, end: date, how: str) -> float:
    mask = (work["_d"] >= start) & (work["_d"] <= end)
    return _agg(work.loc[mask, col], how)


def _pct_change(cur: float, prev: float) -> float | None:
    if _is_na(cur) or _is_na(prev) or prev == 0:
        return None
    return (cur - prev) / prev * 100


def _wow_bounds(as_of: date) -> tuple[date, date, date, date]:
    """(cur_start, cur_end, prev_start, prev_end) for rolling 7d vs prior 7d."""
    cur_start = as_of - timedelta(days=6)
    prev_end = cur_start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return cur_start, as_of, prev_start, prev_end


def _mtd_bounds(as_of: date) -> tuple[date, date, date, date]:
    """(cur_start, cur_end, prev_start, prev_end) for MTD vs prior month same days."""
    cur_start = as_of.replace(day=1)
    if as_of.month == 1:
        prev_start = date(as_of.year - 1, 12, 1)
    else:
        prev_start = date(as_of.year, as_of.month - 1, 1)
    prev_days = days_in_month(prev_start)
    prev_end = prev_start.replace(day=min(as_of.day, prev_days))
    return cur_start, as_of, prev_start, prev_end


def _pooled_ratio(
    work: pd.DataFrame, num_col: str, den_col: str, start: date, end: date
) -> float | None:
    """Σ(numerator) / Σ(denominator) over a window - the correct way to aggregate
    a ratio across days (NOT the mean of daily ratios, which over-weights
    low-denominator days)."""
    num = _range_value(work, num_col, start, end, "sum")
    den = _range_value(work, den_col, start, end, "sum")
    return (num / den) if den else None


def rolling_wow(daily: pd.DataFrame, col: str, as_of: date, how: str) -> dict:
    """Last 7 days vs the prior 7 days (rolling, not calendar weeks)."""
    work = _with_date(daily)
    cur_start, cur_end, prev_start, prev_end = _wow_bounds(as_of)
    cur = _range_value(work, col, cur_start, cur_end, how)
    prev = _range_value(work, col, prev_start, prev_end, how)
    return {"current": cur, "previous": prev, "pct": _pct_change(cur, prev)}


def mtd_same_period(daily: pd.DataFrame, col: str, as_of: date, how: str) -> dict:
    """Current month so far vs the prior month over the same number of days."""
    work = _with_date(daily)
    cur_start, cur_end, prev_start, prev_end = _mtd_bounds(as_of)
    cur = _range_value(work, col, cur_start, cur_end, how)
    prev = _range_value(work, col, prev_start, prev_end, how)
    return {"current": cur, "previous": prev, "pct": _pct_change(cur, prev)}


def target_status(actual: float, target: float, projection: float) -> tuple[str, str]:
    """(css_class, label) from actual/projection vs target."""
    if target and actual >= target:
        return "achieved", "Achieved"
    if target and projection >= target:
        return "ontrack", "On track"
    if target and projection >= AT_RISK_FLOOR * target:
        return "atrisk", "At risk"
    return "offtrack", "Off track"


# --------------------------------------------------------------------------- #
# Section builders
# --------------------------------------------------------------------------- #
def _company_month_row(monthly: pd.DataFrame, as_of: date) -> pd.Series | None:
    if monthly.empty:
        return None
    rolled = monthly.groupby("effective_month", as_index=False).sum(numeric_only=True)
    month_start = pd.Timestamp(as_of.replace(day=1))
    match = rolled[rolled["effective_month"] == month_start]
    if match.empty:
        match = rolled.sort_values("effective_month").tail(1)
    return match.iloc[0] if not match.empty else None


def build_targets(monthly: pd.DataFrame, as_of: date) -> list[dict]:
    row = _company_month_row(monthly, as_of)
    if row is None:
        return []
    d_elapsed = as_of.day
    n_days = days_in_month(as_of)
    out: list[dict] = []
    for spec in TARGET_METRICS:
        actual = float(row.get(spec["actual_col"], 0) or 0)
        target = float(row.get(spec["target_col"], 0) or 0)
        expected_pace = target * d_elapsed / n_days if n_days else 0
        projection = actual / d_elapsed * n_days if d_elapsed else actual
        pct_of_target = (actual / target * 100) if target else None
        css, label = target_status(actual, target, projection)
        out.append(
            {
                "label": spec["label"],
                "actual": actual,
                "actual_fmt": _fmt_value(actual, spec["fmt"]),
                "expected_pace_fmt": _fmt_value(expected_pace, spec["fmt"]),
                "pct_of_target": pct_of_target,
                "pct_of_target_fmt": "n/a" if pct_of_target is None else f"{pct_of_target:.1f}%",
                "projected_fmt": _fmt_value(projection, spec["fmt"]),
                "projected": projection,
                "target": target,
                "target_fmt": _fmt_value(target, spec["fmt"]),
                "status": css,
                "status_label": label,
            }
        )
    return out


def build_regional(monthly: pd.DataFrame, as_of: date) -> list[dict]:
    if monthly.empty:
        return []
    month_start = pd.Timestamp(as_of.replace(day=1))
    cur = monthly[monthly["effective_month"] == month_start]
    if cur.empty:
        latest = monthly["effective_month"].max()
        cur = monthly[monthly["effective_month"] == latest]
    total = float(cur["actual_net_trade_revenue_usd"].sum()) or 0.0
    d_elapsed = as_of.day
    n_days = days_in_month(as_of)
    out: list[dict] = []
    for _, r in cur.sort_values("actual_net_trade_revenue_usd", ascending=False).iterrows():
        actual = float(r["actual_net_trade_revenue_usd"] or 0)
        target = float(r["target_net_trade_revenue_usd"] or 0)
        projection = actual / d_elapsed * n_days if d_elapsed else actual
        pct_of_target = (actual / target * 100) if target else None
        css, label = target_status(actual, target, projection)
        out.append(
            {
                "region": r["region"],
                "revenue_fmt": fmt_usd(actual),
                "pct_of_total": (actual / total * 100) if total else 0,
                "pct_of_total_fmt": f"{(actual / total * 100) if total else 0:.0f}%",
                "pct_of_target_fmt": "n/a" if pct_of_target is None else f"{pct_of_target:.0f}%",
                "status": css,
                "status_label": label,
            }
        )
    return out


def build_cost(instrument: pd.DataFrame, daily: pd.DataFrame, as_of: date) -> dict | None:
    """Trade-revenue composition for the Revenue Analysis section.

    Gross (trade) revenue decomposes into three drivers, all earned on trading
    activity::

        trade revenue = company P&L + gross fees - cashback

    where:
      * ``company_pnl_usd``  - the broker's P&L on client trading (the opposite
        sign of client P&L); typically the largest driver.
      * ``trade_cost_usd``   - fee/commission income we *earn* on volume
        (spread/commission), independent of client P&L. Labelled "gross fees".
      * ``cashback_usd``     - rebate we *return* to clients.

    The table is grouped by instrument group (FX Majors, Metals, Crypto) showing
    each driver and the resulting trade revenue. Two instruments are surfaced as
    headlines: the top P&L contributor and the top fee contributor.
    """
    if instrument is None or instrument.empty:
        return None
    work = _with_date(instrument)
    month_start = as_of.replace(day=1)
    mtd = work[(work["_d"] >= month_start) & (work["_d"] <= as_of)]
    if mtd.empty:
        return None

    def _sum(frame: pd.DataFrame, col: str) -> float:
        return float(pd.to_numeric(frame[col], errors="coerce").sum())

    total_pnl = _sum(mtd, "company_pnl_usd")
    total_fees = _sum(mtd, "trade_cost_usd")
    total_cashback = _sum(mtd, "cashback_usd")
    total_rev = _sum(mtd, "trade_revenue_usd")
    fees_pct_of_rev = (total_fees / total_rev * 100) if total_rev else None
    pnl_pct_of_rev = (total_pnl / total_rev * 100) if total_rev else None

    by_group = (
        mtd.groupby("symbol_group", as_index=False)[
            ["company_pnl_usd", "trade_cost_usd", "cashback_usd", "trade_revenue_usd"]
        ]
        .sum()
        .sort_values("trade_revenue_usd", ascending=False)
    )
    groups = [
        {
            "group": r["symbol_group"],
            "pnl_fmt": fmt_usd(float(r["company_pnl_usd"] or 0)),
            "fees_fmt": fmt_usd(float(r["trade_cost_usd"] or 0)),
            "cashback_fmt": fmt_usd(float(r["cashback_usd"] or 0)),
            "revenue_fmt": fmt_usd(float(r["trade_revenue_usd"] or 0)),
            "pct_of_rev_fmt": (
                f"{(float(r['trade_revenue_usd'] or 0) / total_rev * 100):.0f}%"
                if total_rev
                else "n/a"
            ),
        }
        for _, r in by_group.head(3).iterrows()
    ]

    by_instr = mtd.groupby(["symbol_nickname", "symbol_group"], as_index=False)[
        ["company_pnl_usd", "trade_cost_usd"]
    ].sum()
    top_pnl = by_instr.sort_values("company_pnl_usd", ascending=False).iloc[0] if not by_instr.empty else None
    top_fee = by_instr.sort_values("trade_cost_usd", ascending=False).iloc[0] if not by_instr.empty else None

    return {
        "total_rev_fmt": fmt_usd(total_rev),
        "total_pnl_fmt": fmt_usd(total_pnl),
        "total_fees_fmt": fmt_usd(total_fees),
        "total_cashback_fmt": fmt_usd(total_cashback),
        "fees_pct_of_rev_fmt": "n/a" if fees_pct_of_rev is None else f"{fees_pct_of_rev:.1f}%",
        "pnl_pct_of_rev_fmt": "n/a" if pnl_pct_of_rev is None else f"{pnl_pct_of_rev:.1f}%",
        "groups": groups,
        "top_pnl_instrument": None if top_pnl is None else top_pnl["symbol_nickname"],
        "top_pnl_group": None if top_pnl is None else top_pnl["symbol_group"],
        "top_pnl_fmt": None if top_pnl is None else fmt_usd(float(top_pnl["company_pnl_usd"] or 0)),
        "top_fee_instrument": None if top_fee is None else top_fee["symbol_nickname"],
        "top_fee_group": None if top_fee is None else top_fee["symbol_group"],
        "top_fee_fmt": None if top_fee is None else fmt_usd(float(top_fee["trade_cost_usd"] or 0)),
    }


def _wow_cell(daily: pd.DataFrame, col: str, as_of: date) -> dict:
    cfg = METRICS[col]
    how = cfg["agg"]
    wow = rolling_wow(daily, col, as_of, how)
    pct = wow["pct"]
    # Withdrawal ratio is reported as a points move, not a %.
    if cfg["fmt"] == "ratio":
        delta_pts = (wow["current"] - wow["previous"]) * 100 if not _is_na(wow["current"]) else None
        delta_fmt = "n/a" if _is_na(delta_pts) else f"{delta_pts:+.1f} pts"
        rose = (delta_pts or 0) > 0
    else:
        delta_fmt = "n/a" if _is_na(pct) else f"{pct:+.1f}% WoW"
        rose = (pct or 0) > 0
    arrow = "\u25b2" if rose else "\u25bc"
    good = (cfg["good"] == "up" and rose) or (cfg["good"] == "down" and not rose)
    return {
        "arrow": arrow,
        "delta_fmt": f"{arrow} {delta_fmt.lstrip('+')}" if delta_fmt != "n/a" else "n/a",
        "css": "up" if good else "down",
        "pct": pct,
    }


def _ratio_pts_delta(cur: float, prev: float, good: str = "down", suffix: str = "") -> dict:
    """Points-move delta for a 0..1 ratio metric, coloured by favourable direction.

    ``css`` is ``up`` (green) when the move is favourable, ``down`` (red) otherwise,
    so a falling ratio that we *want* to fall is shown in green.
    """
    if _is_na(cur) or _is_na(prev):
        return {"fmt": "n/a", "css": "down"}
    pts = (cur - prev) * 100
    rose = pts > 0
    arrow = "\u25b2" if rose else "\u25bc"
    good_move = (good == "down" and not rose) or (good == "up" and rose)
    return {"fmt": f"{arrow} {abs(pts):.1f} pts{suffix}", "css": "up" if good_move else "down"}


def _withdrawal_ratio_tile(daily: pd.DataFrame, as_of: date) -> dict:
    """Withdrawal ratio shown as MTD (monthly) on top + the rolling 7-day figure
    below, each with its own change and a 'lower is better' note so the green
    colour (a falling ratio) is unambiguous.

    Computed as a *pooled* ratio (Σ withdrawals / Σ deposits over the window),
    not the mean of daily ratios, so multi-day windows aggregate correctly.
    """
    work = _with_date(daily)
    num, den = "withdrawals_usd", "gross_deposits_usd"
    m_cs, m_ce, m_ps, m_pe = _mtd_bounds(as_of)
    w_cs, w_ce, w_ps, w_pe = _wow_bounds(as_of)
    mtd_cur = _pooled_ratio(work, num, den, m_cs, m_ce)
    mtd_prev = _pooled_ratio(work, num, den, m_ps, m_pe)
    week_cur = _pooled_ratio(work, num, den, w_cs, w_ce)
    week_prev = _pooled_ratio(work, num, den, w_ps, w_pe)
    mtd_delta = _ratio_pts_delta(mtd_cur, mtd_prev, suffix=" vs last month")
    week_delta = _ratio_pts_delta(week_cur, week_prev, suffix=" WoW")
    return {
        "label": "Withdrawal Ratio (MTD)",
        "value_fmt": fmt_ratio_pct(mtd_cur),
        "delta_fmt": mtd_delta["fmt"],
        "delta_css": mtd_delta["css"],
        "sub": "No target \u00b7 the lower the better",
        "secondary_label": "Last 7 days",
        "secondary_fmt": fmt_ratio_pct(week_cur),
        "secondary_delta_fmt": week_delta["fmt"],
        "secondary_delta_css": week_delta["css"],
        "has_target": False,
    }


def build_scorecard(daily: pd.DataFrame, targets: list[dict], as_of: date) -> list[dict]:
    target_by_label = {t["label"]: t for t in targets}
    plan = [
        ("net_revenue_usd", "Net Revenue (MTD)", "sum", "Net trade revenue"),
        ("active_users", "Active Traders (avg/day)", "mean", "Active traders"),
        ("gross_deposits_usd", "Gross Deposits (MTD)", "sum", "Gross deposits"),
        ("withdrawal_ratio", "Withdrawal Ratio", "mean", None),
    ]
    tiles: list[dict] = []
    for col, label, how, target_label in plan:
        if col not in daily.columns:
            continue
        if col == "withdrawal_ratio":
            tiles.append(_withdrawal_ratio_tile(daily, as_of))
            continue
        cfg = METRICS[col]
        if how == "sum":
            value = mtd_same_period(daily, col, as_of, "sum")["current"]
        else:
            value = rolling_wow(daily, col, as_of, "mean")["current"]
        mtd = mtd_same_period(daily, col, as_of, how)
        wow_cell = _wow_cell(daily, col, as_of)
        tile = {
            "label": label,
            "value_fmt": _fmt_value(value, cfg["fmt"]),
            "delta_fmt": wow_cell["delta_fmt"],
            "delta_css": wow_cell["css"],
            "sub": (
                "No target \u00b7 watch metric"
                if target_label is None
                else f"vs prior month (same days): {fmt_signed_pct(mtd['pct'])}"
            ),
            "has_target": target_label is not None,
        }
        if target_label and target_label in target_by_label:
            tile["status"] = target_by_label[target_label]["status"]
            tile["status_label"] = target_by_label[target_label]["status_label"]
        tiles.append(tile)
    return tiles


def build_anomalies(daily: pd.DataFrame, as_of: date) -> dict:
    found: list[dict] = []
    for col, label in (
        ("withdrawals_usd", "Withdrawals"),
        ("net_revenue_usd", "Net revenue"),
        ("net_flow_usd", "Net flow"),
    ):
        if col not in daily.columns:
            continue
        for a in anomalies_mod.zscore_outliers(daily, col, label, as_of):
            found.append(
                {
                    "label": label,
                    "when": a.when,
                    "value_fmt": fmt_usd(a.value),
                    "z_score": a.z_score,
                    "direction": a.direction,
                    "text": (
                        f"{label} on {a.when}: unusually {a.direction} "
                        f"({fmt_usd(a.value)}, ~{abs(a.z_score):.1f} std devs from the 30-day mean)."
                    ),
                }
            )
    rule = anomalies_mod.withdrawal_ratio_rule(daily, as_of)
    rules = [{"label": rule.label, "text": rule.detail, "severity": rule.severity}] if rule else []
    return {"outliers": found, "rules": rules}


def build_forecast(daily: pd.DataFrame, targets: list[dict], as_of: date) -> list[dict]:
    target_by_metric = {
        "net_revenue_usd": next((t for t in targets if t["label"] == "Net trade revenue"), None),
        "gross_deposits_usd": next((t for t in targets if t["label"] == "Gross deposits"), None),
    }
    out: list[dict] = []
    for col, label in (
        ("net_revenue_usd", "Net trade revenue"),
        ("gross_deposits_usd", "Gross deposits"),
        ("net_flow_usd", "Net flow"),
    ):
        if col not in daily.columns:
            continue
        fc = project_month_end(daily, col, as_of, prefer="linear_regression")
        tgt = target_by_metric.get(col)
        out.append(
            {
                "label": label,
                "projected_fmt": fmt_usd(fc.projected_month_end),
                "method": fc.method,
                "target_fmt": tgt["target_fmt"] if tgt else None,
                "has_target": tgt is not None,
            }
        )
    return out


def build_new_users(daily: pd.DataFrame, as_of: date) -> dict | None:
    if "new_users" not in daily.columns:
        return None
    mtd = mtd_same_period(daily, "new_users", as_of, "sum")
    wow = rolling_wow(daily, "new_users", as_of, "sum")
    d_elapsed = as_of.day
    per_day = mtd["current"] / d_elapsed if d_elapsed else mtd["current"]
    return {
        "mtd_fmt": fmt_int(mtd["current"]),
        "mtd_pct": fmt_signed_pct(mtd["pct"]),
        "per_day_fmt": fmt_int(per_day),
        "wow_pct": fmt_signed_pct(wow["pct"]),
    }


# --------------------------------------------------------------------------- #
# Facts text for the LLM
# --------------------------------------------------------------------------- #
def _facts_text(ctx: dict) -> str:
    lines: list[str] = [f"As of {ctx['meta']['as_of']} ({ctx['meta']['period_label']})."]

    lines.append("\nScorecard (rolling 7d WoW; MTD vs prior month same days):")
    for t in ctx["scorecard"]:
        bits = f"- {t['label']}: {t['value_fmt']} | {t['delta_fmt']} | {t['sub']}"
        if t.get("secondary_fmt"):
            bits += (
                f" | {t['secondary_label']}: {t['secondary_fmt']} "
                f"({t.get('secondary_delta_fmt', 'n/a')})"
            )
        if t.get("status_label"):
            bits += f" | target status: {t['status_label']}"
        lines.append(bits)

    lines.append("\nTarget attainment (only these three have plan targets; do not invent others):")
    for t in ctx["targets"]:
        lines.append(
            f"- {t['label']}: actual {t['actual_fmt']} ({t['pct_of_target_fmt']} of target "
            f"{t['target_fmt']}), expected pace {t['expected_pace_fmt']}, "
            f"run-rate projection {t['projected_fmt']} -> {t['status_label']}"
        )

    lines.append("\nRegional net trade revenue vs target:")
    for r in ctx["regional"]:
        lines.append(
            f"- {r['region']}: {r['revenue_fmt']} ({r['pct_of_total_fmt']} of total, "
            f"{r['pct_of_target_fmt']} of target) -> {r['status_label']}"
        )

    if ctx.get("cost"):
        c = ctx["cost"]
        lines.append(
            f"\nTrade revenue composition (MTD): {c['total_rev_fmt']} gross trade revenue "
            f"= company P&L {c['total_pnl_fmt']} ({c['pnl_pct_of_rev_fmt']} of revenue) "
            f"+ gross fees {c['total_fees_fmt']} ({c['fees_pct_of_rev_fmt']} of revenue; "
            f"commission/spread earned independent of client P&L) "
            f"- cashback returned {c['total_cashback_fmt']}."
        )
        for g in c["groups"]:
            lines.append(
                f"- {g['group']}: trade revenue {g['revenue_fmt']} ({g['pct_of_rev_fmt']} of total) "
                f"= P&L {g['pnl_fmt']} + fees {g['fees_fmt']} - cashback {g['cashback_fmt']}"
            )
        if c.get("top_pnl_instrument"):
            lines.append(
                f"- Top P&L instrument: {c['top_pnl_instrument']} "
                f"({c['top_pnl_group']}) at {c['top_pnl_fmt']}."
            )
        if c.get("top_fee_instrument"):
            lines.append(
                f"- Top fee contributor instrument: {c['top_fee_instrument']} "
                f"({c['top_fee_group']}) at {c['top_fee_fmt']}."
            )

    if ctx.get("new_users"):
        nu = ctx["new_users"]
        lines.append(
            f"\nNew users: {nu['mtd_fmt']} MTD ({nu['mtd_pct']} vs prior month), "
            f"~{nu['per_day_fmt']}/day."
        )
    else:
        lines.append("\nNew users: not yet available in the warehouse (pending a dbt field).")

    if ctx["anomalies"]["outliers"] or ctx["anomalies"]["rules"]:
        lines.append("\nAnomalies / risks:")
        for a in ctx["anomalies"]["outliers"]:
            lines.append(f"- {a['text']}")
        for r in ctx["anomalies"]["rules"]:
            lines.append(f"- {r['label']}: {r['text']}")
    else:
        lines.append("\nAnomalies / risks: none flagged.")

    lines.append("\nForecast (month-end):")
    for f in ctx["forecast"]:
        tgt = f" vs target {f['target_fmt']}" if f["has_target"] else " (no target)"
        lines.append(f"- {f['label']}: {f['projected_fmt']}{tgt}. Method: {f['method']}")

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def build_inputs(
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    as_of: date,
    data_range: tuple[str | None, str | None] = (None, None),
    instrument: pd.DataFrame | None = None,
) -> dict:
    """Compute the full structured payload for one report run."""
    period_label = f"Month-to-date ({as_of.strftime('%B %Y')})"
    targets = build_targets(monthly, as_of)
    wow_cur_start = as_of - timedelta(days=6)
    wow_prev_end = wow_cur_start - timedelta(days=1)
    wow_prev_start = wow_prev_end - timedelta(days=6)

    def _fmt_range(start: date, end: date) -> str:
        return f"{start.strftime('%d %b')} \u2013 {end.strftime('%d %b')}"

    ctx: dict = {
        "meta": {
            "as_of": as_of.isoformat(),
            "as_of_display": as_of.strftime("%d %B %Y"),
            "period_label": period_label,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "month_day": as_of.day,
            "month_days": days_in_month(as_of),
            "wow_current_range": _fmt_range(wow_cur_start, as_of),
            "wow_prior_range": _fmt_range(wow_prev_start, wow_prev_end),
            "data_earliest": data_range[0],
            "data_latest": data_range[1],
            "model": "",
            "tokens": 0,
        },
        "targets": targets,
        "scorecard": build_scorecard(daily, targets, as_of),
        "regional": build_regional(monthly, as_of),
        "anomalies": build_anomalies(daily, as_of),
        "forecast": build_forecast(daily, targets, as_of),
        "new_users": build_new_users(daily, as_of),
        "cost": build_cost(instrument, daily, as_of) if instrument is not None else None,
    }
    ctx["facts"] = _facts_text(ctx)
    return ctx
