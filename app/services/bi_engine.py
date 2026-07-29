"""Orchestration for the BI Assistant turn.

Pipeline (LLM interprets, warehouse computes):
  1. Plan  — LLM picks allowlisted metric(s) + dimension(s) + time range (JSON).
  2. Run   — MetricFlow compiles & executes; we never write SQL.
  3. Derive— optional period-over-period (MoM/WoW) computed in pandas.
  4. Explain — LLM writes a concise analyst answer over the returned numbers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from services import ai_client
from services.metrics import (
    MetricQuery,
    MetricQueryError,
    build_filters,
    get_data_date_range,
    run_metric_query,
)
from services.semantic import format_catalog_for_prompt, render_catalog_markdown

_CATALOG_HINTS = (
    "what metric",
    "which metric",
    "what can you",
    "what dimensions",
    "which dimensions",
    "what data can",
    "what are the metrics",
    "list the metrics",
    "report on",
    "help",
)


@dataclass
class TurnResult:
    answer: str
    intent: str  # "catalog" | "metric_query" | "refuse" | "error"
    queries: list[dict] = field(default_factory=list)  # describe() dicts
    frames: list[pd.DataFrame] = field(default_factory=list)
    chart: dict | None = None
    title: str = ""
    model: str = ""
    tier: str = ""
    total_tokens: int = 0
    pop_summary: pd.DataFrame | None = None
    anomalies: pd.DataFrame | None = None


def _looks_like_catalog_question(question: str) -> bool:
    text = question.lower().strip()
    if len(text) < 60 and any(h in text for h in _CATALOG_HINTS):
        return True
    return False


def _planner_system_prompt(latest: str | None, earliest: str | None) -> str:
    today = date.today().isoformat()
    return f"""You are the query planner for a fintech BI assistant.

You DO NOT write SQL. You may ONLY choose metrics and dimensions from the
allowlist below. The app runs them through dbt MetricFlow.

DATE CONTEXT
- Real calendar today: {today}
- Warehouse data covers: {earliest or "?"} to {latest or "?"}
- Treat the LATEST data date ({latest or "?"}) as "now" for relative ranges
  like "last 7 days" or "this month".

CONVERSATION CONTEXT
- You may be given the last few turns of the conversation. Use them ONLY to
  resolve follow-up references (e.g. "that region", "those users", "same period",
  "what about Europe?").
- Always output a COMPLETE, self-contained plan for the CURRENT question — do not
  assume the app remembers earlier filters.

ALLOWLIST (metric [type] — label. dimensions: ... time: ...):
{format_catalog_for_prompt()}

GROUP-BY RULES
- Time series: use a metric_time grain, e.g. "metric_time__day" or
  "metric_time__month".
- Categorical splits: use the exact dimension names shown for that metric
  (e.g. "user_day__reporting_region").
- Only combine a metric with dimensions listed for that metric.
- High cardinality: when grouping by an individual identifier such as
  "user_day__user_id", ALWAYS set "order" to the metric descending
  (e.g. ["-net_revenue"]) and a small "limit" (e.g. 10), and prefer a bar chart.

OUTPUT — respond with ONLY a JSON object (no prose, no markdown fences):
{{
  "intent": "metric_query" | "catalog" | "refuse",
  "refusal_reason": "if refuse: explain briefly and suggest the closest allowed metric or the Executive Dashboard",
  "title": "short human title for the result",
  "queries": [
    {{
      "metrics": ["metric_name"],
      "group_by": ["metric_time__day"],
      "start_time": "YYYY-MM-DD",
      "end_time": "YYYY-MM-DD",
      "order": ["metric_time__day"],
      "limit": 500,
      "filters": [
        {{ "dimension": "user_day__reporting_region", "operator": "=", "value": "Europe" }}
      ]
    }}
  ],
  "post_processing": "none" | "period_over_period",
  "chart": {{ "type": "line" | "bar" | "stacked_bar" | "none",
              "x": "column_name", "y": "metric_name_or_list", "color": "column_name_or_null" }}
}}

CHART RULES — only add a chart when it genuinely helps; otherwise use "none":
- "none": single-value answers, simple lookups, top-N lists already clear as a
  table, or yes/no questions.
- "line": a metric trending over time (x = a metric_time grain).
- "bar": comparing a metric across categories (x = a categorical dimension).
- "stacked_bar": a metric over time split by ONE category (x = time, color = dim).
- Multi-metric overview over time: set "x" to the metric_time grain and "y" to a
  LIST of the metric names; the app renders one small sparkline per metric.

RULES
- For "month over month"/"MOM" or "week over week"/"WOW": set
  post_processing="period_over_period", group by the matching metric_time grain
  (month or week) plus any split dimension, and span at least the two relevant
  periods in the time range.
- For questions about anomalies, spikes, drops, surges, or "unusual" activity:
  do NOT refuse. Plan a DAILY time series (group_by ["metric_time__day"]) of the
  most relevant metric (usually net_revenue, gross_revenue, or net_flow) over a
  ~30-day window ending at the latest data date, set
  post_processing="anomaly_scan", and chart type "line". The app flags outliers.
- For "why", "root cause", "driver", or "what's driving" questions: do NOT
  refuse. You cannot prove causation, but you CAN surface where the movement
  came from. Plan the most relevant metric broken down by the most informative
  dimension available for it (e.g. region, country, instrument) and/or as a
  daily time series, so the explanation can point at the segments or dates that
  moved the most. Certainty is not required.
- Only refuse if the question needs a metric or dimension that genuinely does not
  exist in the allowlist (then set intent="refuse").
- Column names in "chart" must be the metric names and group_by names you chose.

FILTER RULES (focusing on a specific value, e.g. one region/country/user)
- To restrict to a single value (e.g. "Europe only", "for Germany", "user 2100"),
  add a "filters" entry with the dimension, operator ("=", "!=", "in", etc.) and
  value. Do NOT just drop the dimension — that returns the company total.
- "operator": one of = , != , > , < , >= , <= , in. For "in", value is a list.
- Never filter on metric_time via filters — use start_time/end_time instead.
- You may omit "filters" (or use []) when no value restriction is needed.
"""


# Reasoning models (Pro) spend a large, hidden share of their budget on
# reasoning before emitting the JSON plan. With too small a cap the JSON is
# truncated and unparseable, so the planner gets generous headroom.
_PLANNER_MAX_TOKENS = 2000


def _alt_tier(tier: str) -> str:
    return "flash" if tier == "pro" else "pro"


def _plan_turn(planner_messages: list[dict], preferred_tier: str):
    """Plan the turn, retrying on the other tier if the JSON is unusable.

    The Pro tier is a reasoning model and occasionally returns empty/truncated
    content for a strict-JSON request. Rather than failing outright (Pro had no
    safety net before), we retry on the alternate tier so a question still gets
    answered. Returns ``(plan_dict_or_None, last_response_or_None)``.
    """
    last_error: ai_client.LLMError | None = None
    last_resp: ai_client.LLMResponse | None = None
    for attempt_tier in dict.fromkeys([preferred_tier, _alt_tier(preferred_tier)]):
        try:
            resp = ai_client.chat(
                planner_messages,
                tier=attempt_tier,
                max_tokens=_PLANNER_MAX_TOKENS,
                temperature=0.0,
                response_format_json=True,
            )
        except ai_client.LLMError as exc:
            last_error = exc
            continue
        last_resp = resp
        try:
            return _parse_plan(resp.content), resp
        except (json.JSONDecodeError, ValueError):
            continue
    if last_resp is None and last_error is not None:
        raise last_error
    return None, last_resp


def _parse_plan(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def _period_over_period(df: pd.DataFrame, query: MetricQuery) -> pd.DataFrame | None:
    """Compute change between the two latest periods per category."""
    time_cols = [c for c in df.columns if "metric_time__" in c]
    metric_cols = [c for c in df.columns if c in query.metrics]
    if not time_cols or not metric_cols or df.empty:
        return None
    time_col, metric_col = time_cols[0], metric_cols[0]
    cat_cols = [c for c in df.columns if c not in time_cols and c not in metric_cols]

    periods = sorted(df[time_col].dropna().unique())
    if len(periods) < 2:
        return None
    prev_p, curr_p = periods[-2], periods[-1]

    def slice_period(p):
        return df[df[time_col] == p].set_index(cat_cols)[metric_col] if cat_cols else (
            pd.Series({"All": df[df[time_col] == p][metric_col].sum()})
        )

    curr = slice_period(curr_p)
    prev = slice_period(prev_p)
    out = pd.DataFrame({"current": curr, "previous": prev}).fillna(0)
    out["change"] = out["current"] - out["previous"]
    out["change_pct"] = out.apply(
        lambda r: (r["change"] / r["previous"] * 100) if r["previous"] else None, axis=1
    )
    return out.reset_index()


def _anomaly_scan(df: pd.DataFrame, query: MetricQuery, z_threshold: float = 2.0):
    """Flag daily points whose value is >= z_threshold std devs from the mean."""
    time_cols = [c for c in df.columns if "metric_time__" in c]
    metric_cols = [c for c in df.columns if c in query.metrics]
    if not time_cols or not metric_cols or len(df) < 4:
        return None
    tcol, mcol = time_cols[0], metric_cols[0]
    work = df[[tcol, mcol]].dropna().sort_values(tcol).copy()
    vals = pd.to_numeric(work[mcol], errors="coerce")
    mean, std = vals.mean(), vals.std()
    if not std or pd.isna(std):
        return None
    work["z_score"] = ((vals - mean) / std).round(2)
    work["vs_mean"] = (vals - mean).round(0)
    flagged = work[work["z_score"].abs() >= z_threshold]
    if flagged.empty:
        return None
    flagged = flagged.copy()
    flagged[tcol] = pd.to_datetime(flagged[tcol]).dt.date.astype(str)
    return flagged.reset_index(drop=True)


def _analysis_context(df: pd.DataFrame, query: MetricQuery) -> str:
    """Python-computed facts that help the LLM reason without inventing numbers."""
    if df.empty:
        return ""
    time_cols = [c for c in df.columns if "metric_time__" in c]
    metric_cols = [c for c in df.columns if c in query.metrics]
    cat_cols = [c for c in df.columns if c not in time_cols and c not in metric_cols]
    lines: list[str] = []

    for mcol in metric_cols:
        series = pd.to_numeric(df[mcol], errors="coerce").dropna()
        if series.empty:
            continue
        lines.append(
            f"{mcol}: total={series.sum():,.0f}, mean={series.mean():,.0f}, "
            f"min={series.min():,.0f}, max={series.max():,.0f}, n={len(series)}"
        )

        if time_cols:
            tcol = time_cols[0]
            ordered = df[[tcol, mcol]].dropna().sort_values(tcol)
            vals = pd.to_numeric(ordered[mcol], errors="coerce")
            if len(ordered) >= 2:
                first, last = vals.iloc[0], vals.iloc[-1]
                d0 = pd.to_datetime(ordered[tcol].iloc[0]).date()
                d1 = pd.to_datetime(ordered[tcol].iloc[-1]).date()
                pct = f" ({(last - first) / first * 100:+.1f}%)" if first else ""
                lines.append(
                    f"  trend {mcol}: {first:,.0f} ({d0}) -> {last:,.0f} ({d1}), "
                    f"change={last - first:,.0f}{pct}"
                )
                imax, imin = vals.idxmax(), vals.idxmin()
                lines.append(
                    f"  peak={vals.loc[imax]:,.0f} on "
                    f"{pd.to_datetime(ordered.loc[imax, tcol]).date()}; "
                    f"trough={vals.loc[imin]:,.0f} on "
                    f"{pd.to_datetime(ordered.loc[imin, tcol]).date()}"
                )

        if cat_cols and not time_cols:
            grp = (
                df.groupby(cat_cols[0])[mcol]
                .sum()
                .sort_values(ascending=False)
            )
            total = grp.sum()
            if len(grp):
                top_k, top_v = grp.index[0], grp.iloc[0]
                bot_k, bot_v = grp.index[-1], grp.iloc[-1]
                share = f" ({top_v / total * 100:.0f}% of total)" if total else ""
                lines.append(
                    f"  by {cat_cols[0]}: highest={top_k} ({top_v:,.0f}{share}), "
                    f"lowest={bot_k} ({bot_v:,.0f})"
                )
    return "\n".join(lines)


def _frame_to_markdown(df: pd.DataFrame, max_rows: int = 40) -> str:
    show = df.head(max_rows).copy()
    for col in show.columns:
        if pd.api.types.is_datetime64_any_dtype(show[col]):
            show[col] = show[col].dt.date.astype(str)
    try:
        return show.to_markdown(index=False)
    except Exception:
        return show.to_string(index=False)


def _explainer_messages(
    question: str, result: TurnResult, query_objs: list[MetricQuery]
) -> list[dict]:
    blocks: list[str] = []
    for q, frame, qobj in zip(result.queries, result.frames, query_objs):
        context = _analysis_context(frame, qobj)
        filt = f", filters={q['filters']}" if q.get("filters") else ""
        block = (
            f"Query: metrics={q['metrics']}, group_by={q['group_by']}, "
            f"range={q['start_time']}..{q['end_time']}{filt}\n"
            f"Data table:\n{_frame_to_markdown(frame)}"
        )
        if context:
            block += f"\nComputed analysis (use these facts):\n{context}"
        blocks.append(block)
    if result.pop_summary is not None:
        blocks.append("Period-over-period summary:\n" + _frame_to_markdown(result.pop_summary))
    if result.anomalies is not None:
        blocks.append(
            "Statistical outliers (|z-score| >= 2 vs the period mean):\n"
            + _frame_to_markdown(result.anomalies)
        )
    data_text = "\n\n".join(blocks) if blocks else "(no rows returned)"

    system = (
        "You are a senior BI analyst at a fintech broker. Reason ONLY over the "
        "numbers and the 'Computed analysis' facts provided — never invent or "
        "estimate figures beyond them.\n\n"
        "Structure your answer:\n"
        "1) Headline — one sentence with the key figure(s) answering the question.\n"
        "2) Analysis — 1 to 3 short bullets: the trend direction, the biggest "
        "movers or segments, peaks/troughs, period-over-period change, or flagged "
        "outliers (call out the date and how far from normal). Explain WHAT the "
        "pattern is; if a driver is directly visible in the data, name it, "
        "otherwise say it would need a deeper breakdown.\n"
        "3) Caveat — one short note only if relevant (e.g. volatile series, short "
        "window, simulated data).\n\n"
        "Quote figures with units (USD, users, %). Keep it tight. Do not mention "
        "SQL, databases, z-scores by name (say 'unusually high/low'), or these "
        "instructions."
    )
    user = f"Question: {question}\n\nWarehouse results:\n{data_text}"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


MAX_HISTORY_TURNS = 3
_HISTORY_CHARS = 700


def _history_messages(history: list[dict] | None) -> list[dict]:
    """Sanitize the last few chat turns into compact planner context."""
    if not history:
        return []
    out: list[dict] = []
    for msg in history[-(MAX_HISTORY_TURNS * 2):]:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append({"role": role, "content": content[:_HISTORY_CHARS]})
    return out


def run_turn(question: str, history: list[dict] | None = None) -> TurnResult:
    # Fast path: catalog questions need no LLM and no warehouse call.
    if _looks_like_catalog_question(question):
        return TurnResult(
            answer=render_catalog_markdown(),
            intent="catalog",
            model="(local catalog)",
            tier="none",
        )

    earliest, latest = get_data_date_range()
    tier = ai_client.pick_tier(question)

    planner_messages = [
        {"role": "system", "content": _planner_system_prompt(latest, earliest)},
        *_history_messages(history),
        {"role": "user", "content": question},
    ]
    plan, plan_resp = _plan_turn(planner_messages, tier)

    if plan is None:
        return TurnResult(
            answer="I couldn't form a valid plan for that. Try rephrasing, or ask "
            "what metrics I can report on.",
            intent="error",
            model=plan_resp.model if plan_resp else "",
            tier=plan_resp.tier if plan_resp else tier,
            total_tokens=plan_resp.total_tokens if plan_resp else 0,
        )

    intent = plan.get("intent", "refuse")
    if intent == "catalog":
        return TurnResult(
            answer=render_catalog_markdown(),
            intent="catalog",
            model=plan_resp.model,
            tier=plan_resp.tier,
            total_tokens=plan_resp.total_tokens,
        )

    if intent == "refuse":
        reason = plan.get("refusal_reason") or (
            "That question can't be answered from the governed metrics. "
            "Try the Executive Dashboard or ask what metrics I can report on."
        )
        return TurnResult(
            answer=reason,
            intent="refuse",
            model=plan_resp.model,
            tier=plan_resp.tier,
            total_tokens=plan_resp.total_tokens,
        )

    # metric_query
    result = TurnResult(
        answer="",
        intent="metric_query",
        chart=plan.get("chart"),
        title=plan.get("title", ""),
        model=plan_resp.model,
        tier=plan_resp.tier,
        total_tokens=plan_resp.total_tokens,
    )

    queries: list[MetricQuery] = []
    try:
        for q in plan.get("queries", []):
            mlist = q.get("metrics", [])
            where, summary = build_filters(mlist, q.get("filters") or [])
            queries.append(
                MetricQuery(
                    metrics=mlist,
                    group_by=q.get("group_by", []),
                    start_time=q.get("start_time"),
                    end_time=q.get("end_time"),
                    order=q.get("order", []),
                    limit=q.get("limit"),
                    where=where,
                    filter_summary=summary,
                )
            )
    except MetricQueryError as exc:
        return TurnResult(
            answer=f"I couldn't apply that filter against the governed metrics: {exc}",
            intent="refuse",
            model=plan_resp.model,
            tier=plan_resp.tier,
            total_tokens=plan_resp.total_tokens,
        )

    if not queries:
        return TurnResult(
            answer="I didn't produce a runnable query. Please rephrase.",
            intent="error",
            model=plan_resp.model,
            tier=plan_resp.tier,
            total_tokens=plan_resp.total_tokens,
        )

    post = plan.get("post_processing", "none")
    try:
        for q in queries:
            frame = run_metric_query(q)
            result.frames.append(frame)
            result.queries.append(q.describe())
            if post == "period_over_period" and result.pop_summary is None:
                result.pop_summary = _period_over_period(frame, q)
            if post == "anomaly_scan" and result.anomalies is None:
                result.anomalies = _anomaly_scan(frame, q)
    except MetricQueryError as exc:
        return TurnResult(
            answer=f"I couldn't run that against the governed metrics: {exc}",
            intent="refuse",
            queries=result.queries,
            model=plan_resp.model,
            tier=plan_resp.tier,
            total_tokens=plan_resp.total_tokens,
        )

    if all(f.empty for f in result.frames):
        result.answer = (
            "No data was returned for that range. The warehouse currently covers "
            f"{earliest} to {latest}."
        )
        return result

    explain_resp = ai_client.chat(
        _explainer_messages(question, result, queries),
        tier=plan_resp.tier,
        max_tokens=1500,
        temperature=0.2,
    )
    result.total_tokens += explain_resp.total_tokens
    answer = (explain_resp.content or "").strip()
    if not answer:
        # Last-resort grounded summary if the model returned nothing usable.
        answer = _fallback_summary(result, queries)
    result.answer = answer
    return result


def _fallback_summary(result: TurnResult, queries: list[MetricQuery]) -> str:
    parts = ["Here is what the data shows:"]
    for frame, qobj in zip(result.frames, queries):
        ctx = _analysis_context(frame, qobj)
        if ctx:
            parts.append(ctx)
    if result.pop_summary is not None and not result.pop_summary.empty:
        parts.append("Period-over-period:\n" + _frame_to_markdown(result.pop_summary))
    if result.anomalies is not None and not result.anomalies.empty:
        parts.append("Flagged outliers:\n" + _frame_to_markdown(result.anomalies))
    return "\n\n".join(parts)
