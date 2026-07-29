"""BI Assistant — reactive chat grounded in the MetricFlow semantic layer.

The assistant only queries governed metrics/dimensions (no ad-hoc SQL). It
plans a metric request, MetricFlow runs it, and the LLM explains the numbers.
Each answer shows which model replied and the exact query used.
"""

import re
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP_ROOT = Path(__file__).resolve().parent.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from services import ai_client
from services.bi_engine import TurnResult, run_turn

st.set_page_config(page_title="BI Assistant", page_icon="💬", layout="wide")

EXAMPLE_PROMPTS = [
    "What are the metrics and dimensions that you can report on?",
    "How was the revenue last 7 days?",
    "What are active users by region this month and what is the MoM?",
]

HISTORY_TURNS = 3  # conversation turns kept as context for follow-up questions

_TIER_LABEL = {"flash": "Flash", "pro": "Pro", "none": "local"}


def _first_in_cols(value, cols: list[str]):
    """The planner may return a string, a list, or null for a chart axis.

    Return the first value that exists as a column, else None.
    """
    if value is None:
        return None
    candidates = value if isinstance(value, list) else [value]
    for cand in candidates:
        if isinstance(cand, str) and cand in cols:
            return cand
    return None


def _is_time_col(name: str) -> bool:
    return "metric_time__" in name


def _render_sparklines(df, x: str, metric_cols: list[str]) -> None:
    """One small line chart per metric — avoids mixing scales (USD vs users)."""
    ordered = df.sort_values(x)
    chart_cols = st.columns(len(metric_cols))
    for col, metric in zip(chart_cols, metric_cols):
        fig = px.line(ordered, x=x, y=metric, markers=True)
        fig.update_layout(
            margin=dict(l=6, r=6, t=28, b=6),
            height=200,
            title=dict(text=metric, font=dict(size=13)),
            xaxis_title=None,
            yaxis_title=None,
            showlegend=False,
        )
        col.plotly_chart(fig, use_container_width=True)


def _render_chart(result: TurnResult) -> None:
    chart = result.chart or {}
    ctype = chart.get("type", "none")
    if ctype == "none" or not result.frames:
        return
    df = result.frames[0]
    if df.empty:
        return

    cols = list(df.columns)
    x = _first_in_cols(chart.get("x"), cols)
    color = _first_in_cols(chart.get("color"), cols)

    # Support one or several metric columns on the y-axis.
    raw_y = chart.get("y")
    y_candidates = raw_y if isinstance(raw_y, list) else [raw_y]
    y_cols = [c for c in y_candidates if isinstance(c, str) and c in cols]
    if x is None or not y_cols:
        return

    # Multi-metric overview over time → one sparkline per metric (own scale).
    if len(y_cols) > 1 and _is_time_col(x):
        _render_sparklines(df, x, y_cols)
        return

    y = y_cols[0] if len(y_cols) == 1 else y_cols
    if isinstance(y, list):
        color = None  # wide-form y and color are mutually exclusive in plotly.express

    try:
        if ctype == "line":
            fig = px.line(df, x=x, y=y, color=color, markers=True)
        elif ctype == "stacked_bar":
            fig = px.bar(df, x=x, y=y, color=color, barmode="stack")
        else:  # bar
            fig = px.bar(df, x=x, y=y, color=color, barmode="group")
    except Exception:
        return

    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380)
    st.plotly_chart(fig, use_container_width=True)


def _escape_md(text: str) -> str:
    """Escape '$' so Streamlit doesn't render USD amounts as LaTeX math."""
    return re.sub(r"(?<!\\)\$", r"\\$", text or "")


def _render_result(result: TurnResult) -> None:
    st.markdown(_escape_md(result.answer))

    if result.intent == "metric_query":
        _render_chart(result)

        if result.pop_summary is not None and not result.pop_summary.empty:
            st.caption("Period-over-period")
            st.dataframe(result.pop_summary, use_container_width=True, hide_index=True)

        if result.anomalies is not None and not result.anomalies.empty:
            st.caption("Flagged outliers (unusually high/low days)")
            st.dataframe(result.anomalies, use_container_width=True, hide_index=True)

        with st.expander("Query details"):
            for i, (q, frame) in enumerate(zip(result.queries, result.frames), start=1):
                filt = f" · filters `{'; '.join(q['filters'])}`" if q.get("filters") else ""
                st.markdown(
                    f"**Query {i}** · metrics `{', '.join(q['metrics'])}` · "
                    f"group by `{', '.join(q['group_by']) or 'none'}` · "
                    f"range `{q['start_time']} → {q['end_time']}`{filt}"
                )
                st.dataframe(frame, use_container_width=True, hide_index=True)
            st.caption("Metrics computed by dbt MetricFlow in the warehouse — no ad-hoc SQL.")


def _badge(result: TurnResult) -> str:
    tier = _TIER_LABEL.get(result.tier, result.tier or "?")
    bits = [f"model: **{result.model}** ({tier})"]
    if result.total_tokens:
        bits.append(f"{result.total_tokens} tokens")
    return " · ".join(bits)


def _history_for_planner() -> list[dict]:
    """Last few turns (user question + assistant answer) for follow-up context."""
    history: list[dict] = []
    for msg in st.session_state.bi_messages[-(HISTORY_TURNS * 2):]:
        history.append({"role": msg["role"], "content": msg.get("content", "")})
    return history


def _process(question: str) -> None:
    history = _history_for_planner()  # capture BEFORE appending the new question
    st.session_state.bi_messages.append({"role": "user", "content": question})
    with st.spinner("Querying the semantic layer…"):
        try:
            result = run_turn(question, history=history)
        except ai_client.LLMError as exc:
            result = TurnResult(answer=f"LLM error: {exc}", intent="error")
        except Exception as exc:  # noqa: BLE001 — surface any failure in chat
            result = TurnResult(answer=f"Something went wrong: {exc}", intent="error")
    st.session_state.bi_messages.append(
        {"role": "assistant", "content": result.answer, "result": result}
    )


st.title("BI Assistant")
st.caption(
    "Ask about the fintech KPIs. Answers come from governed MetricFlow metrics — "
    "the assistant never writes its own SQL. "
    f"Context is held for the last {HISTORY_TURNS} messages, so you can ask "
    "follow-ups (e.g. *\u201cwhat about Europe?\u201d*)."
)

if "bi_messages" not in st.session_state:
    st.session_state.bi_messages = []

if not ai_client.is_configured():
    st.warning(
        "No OpenRouter API key found. Add `LLM_API_KEY` to your `.env` (see "
        "`.env.example`) and restart Streamlit to enable the assistant. You can "
        'still click "metrics and dimensions" below to browse the catalog.'
    )

st.markdown("**Try one of these:**")
chip_cols = st.columns(len(EXAMPLE_PROMPTS))
for col, prompt in zip(chip_cols, EXAMPLE_PROMPTS):
    if col.button(prompt, use_container_width=True):
        st.session_state.pending_question = prompt

for msg in st.session_state.bi_messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant" and "result" in msg:
            _render_result(msg["result"])
            st.caption(_badge(msg["result"]))
        else:
            st.markdown(msg["content"])

pending = st.session_state.pop("pending_question", None)
typed = st.chat_input("Ask about revenue, active users, deposits, regions…")
question = typed or pending

if question:
    _process(question)
    st.rerun()
