"""Turn the structured inputs into a rendered HTML CFO report.

Workflow:
  1. Build a strict-JSON prompt from the Python-computed ``facts`` and ask the
     CFO model (via ``app.services.ai_client``) for the narrative only - an
     overview paragraph plus, per section, a headline / bullets / detail.
  2. Merge the narrative with the computed numbers and render the Jinja2 HTML
     template.

The LLM writes prose only; every figure in the report (scorecard, target table,
regional table, forecasts) is injected by the template from Python, so the model
cannot alter numbers. If the LLM is unavailable or returns unusable output, a
deterministic fallback narrative keeps the report renderable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_TEMPLATE_NAME = "cfo_report.html.j2"

# Fixed section order and titles. The LLM fills narrative for each id.
SECTIONS: list[tuple[str, str]] = [
    ("exec_summary", "Executive Summary"),
    ("trends_targets", "Monthly Trends vs Targets"),
    ("revenue", "Revenue Analysis"),
    ("user_activity", "User Activity Analysis"),
    ("cash_flow", "Cash Flow Analysis"),
    ("regional", "Regional Performance"),
    ("risks", "Risks & Anomalies"),
    ("forecast", "Forecast Outlook"),
    ("actions", "Recommended Actions"),
]


@dataclass
class ReportResult:
    report_html: str
    narrative: dict
    model: str
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
def _system_prompt() -> str:
    section_list = "\n".join(f'  - "{sid}": {title}' for sid, title in SECTIONS)
    return f"""You are the CFO of a fintech brokerage writing the monthly executive
performance report for the board, in the style of a McKinsey briefing: answer-first,
clear, and context-rich without being verbose. You explain what the numbers mean and
why they matter; you never confuse the reader with jargon.

STRICT RULES
- Use ONLY the figures provided in the facts. NEVER invent, round differently, or
  estimate numbers beyond what is given.
- Targets exist for EXACTLY three metrics (active traders, net trade revenue, gross
  deposits). Never claim a target for any other metric (e.g. net flow, withdrawal
  ratio).
- When you mention a forecast, state the method name exactly as given in the facts.
- Be specific and decision-oriented. Prefer concrete movers, dates, and segments.

Write these nine sections (use the exact ids):
{section_list}

For each section provide:
  - "headline": one formal sentence capturing the key message.
  - "bullets": 2-4 short, concrete bullet strings.
  - "detail": one short paragraph of additional context for a reader who wants more.
Also write a single "overview" paragraph (3-5 sentences) for the top of the report.

OUTPUT: respond with ONLY a JSON object, no markdown fences:
{{
  "overview": "string",
  "sections": {{
    "exec_summary": {{ "headline": "string", "bullets": ["..."], "detail": "string" }},
    "...": {{ ... }}
  }}
}}"""


def _parse_json(content: str) -> dict:
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


# --------------------------------------------------------------------------- #
# Fallback narrative (deterministic, used when the LLM is unavailable)
# --------------------------------------------------------------------------- #
def _fallback_narrative(ctx: dict) -> dict:
    sections: dict[str, dict] = {}
    for sid, title in SECTIONS:
        sections[sid] = {
            "headline": f"{title} (auto-generated summary; LLM narrative unavailable).",
            "bullets": [],
            "detail": "Narrative generation was skipped or failed; the figures above are computed directly from the warehouse.",
        }

    sc = {t["label"]: t for t in ctx["scorecard"]}
    if "Net Revenue (MTD)" in sc:
        sections["revenue"]["bullets"] = [
            f"Net revenue {sc['Net Revenue (MTD)']['value_fmt']} MTD ({sc['Net Revenue (MTD)']['delta_fmt']})."
        ]
    sections["trends_targets"]["bullets"] = [
        f"{t['label']}: {t['pct_of_target_fmt']} of target - {t['status_label']}." for t in ctx["targets"]
    ]
    sections["regional"]["bullets"] = [
        f"{r['region']}: {r['revenue_fmt']} ({r['pct_of_target_fmt']} of target) - {r['status_label']}."
        for r in ctx["regional"]
    ]
    sections["risks"]["bullets"] = [a["text"] for a in ctx["anomalies"]["outliers"]] + [
        f"{r['label']}: {r['text']}." for r in ctx["anomalies"]["rules"]
    ]
    sections["forecast"]["bullets"] = [
        f"{f['label']} month-end estimate: {f['projected_fmt']}"
        + (f" vs target {f['target_fmt']}." if f["has_target"] else " (no target).")
        for f in ctx["forecast"]
    ]
    overview = (
        f"Executive performance report as of {ctx['meta']['as_of_display']} "
        f"({ctx['meta']['period_label']}). All figures are computed in the warehouse; "
        "this run used the deterministic summary because the language model was unavailable."
    )
    return {"overview": overview, "sections": sections}


def _generate_narrative(ctx: dict) -> tuple[dict, str, int, int]:
    """Return (narrative, model, prompt_tokens, completion_tokens)."""
    try:
        from app.services import ai_client
    except Exception as exc:
        logger.warning("LLM client unavailable (%s); using deterministic fallback narrative", exc)
        return _fallback_narrative(ctx), "(fallback)", 0, 0

    if not ai_client.is_configured():
        logger.warning("LLM_API_KEY not configured; using deterministic fallback narrative")
        return _fallback_narrative(ctx), "(fallback - no API key)", 0, 0

    cfg = ai_client.get_config()
    model = cfg["model_cfo"]
    facts_len = len(ctx.get("facts", ""))
    logger.info("Calling LLM for narrative (model=%s, facts_chars=%s)", model, facts_len)
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": f"Facts (warehouse-computed):\n{ctx['facts']}"},
    ]
    try:
        resp = ai_client.chat(
            messages,
            tier="cfo",
            model=model,
            # Headroom for a reasoning model: hidden chain-of-thought + the full
            # nine-section JSON. Keep reasoning effort low so the budget is spent
            # on the visible narrative rather than truncating the JSON.
            max_tokens=8000,
            temperature=0.3,
            response_format_json=True,
            reasoning={"effort": "low"},
        )
        narrative = _parse_json(resp.content)
        if "sections" not in narrative:
            raise ValueError("missing sections")
        section_count = len(narrative.get("sections", {}))
        logger.info(
            "LLM narrative received (model=%s, sections=%s, prompt_tokens=%s, completion_tokens=%s)",
            resp.model,
            section_count,
            resp.prompt_tokens,
            resp.completion_tokens,
        )
        return narrative, resp.model, resp.prompt_tokens, resp.completion_tokens
    except Exception as exc:
        logger.warning("LLM call failed (%s); using deterministic fallback narrative", exc)
        return _fallback_narrative(ctx), "(fallback - LLM error)", 0, 0


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def _ordered_sections(narrative: dict) -> list[dict]:
    nsec = narrative.get("sections", {}) or {}
    out: list[dict] = []
    for i, (sid, title) in enumerate(SECTIONS, start=1):
        n = nsec.get(sid, {}) or {}
        out.append(
            {
                "id": sid,
                "num": f"{i:02d}",
                "title": title,
                "headline": n.get("headline", ""),
                "bullets": n.get("bullets", []) or [],
                "detail": n.get("detail", ""),
            }
        )
    return out


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def generate_report(ctx: dict) -> ReportResult:
    narrative, model, p_tok, c_tok = _generate_narrative(ctx)

    ctx["meta"]["model"] = model
    ctx["meta"]["tokens"] = p_tok + c_tok

    logger.info("Rendering HTML from template %s", _TEMPLATE_NAME)
    template = _environment().get_template(_TEMPLATE_NAME)
    html = template.render(
        meta=ctx["meta"],
        overview=narrative.get("overview", ""),
        scorecard=ctx["scorecard"],
        targets=ctx["targets"],
        regional=ctx["regional"],
        forecast=ctx["forecast"],
        new_users=ctx.get("new_users"),
        cost=ctx.get("cost"),
        sections=_ordered_sections(narrative),
    )
    return ReportResult(
        report_html=html,
        narrative=narrative,
        model=model,
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
    )
