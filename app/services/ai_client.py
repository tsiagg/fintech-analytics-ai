"""OpenRouter client for the BI Assistant.

Cost strategy (target < $15/month):
  * Default model = DeepSeek V4 Flash (cheap, fast) for most questions.
  * Escalate to DeepSeek V4 Pro for root-cause / comparison / anomaly questions,
    or when Flash fails.

The LLM only **plans** which allowlisted metric to query and **explains** the
numbers MetricFlow returns. It never sees raw SQL and never invents figures.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

DEFAULT_API_BASE = "https://openrouter.ai/api/v1"
_DEFAULT_FLASH = "deepseek/deepseek-v4-flash"
_DEFAULT_PRO = "deepseek/deepseek-v4-pro"
_REQUEST_TIMEOUT = 90

# Words that suggest the user wants deeper reasoning → use the Pro model.
_PRO_TRIGGERS = (
    "why",
    "root cause",
    "root-cause",
    "driver",
    "drivers",
    "cause",
    "reason",
    "explain why",
    "anomaly",
    "anomalies",
    "spike",
    "drop",
    "decline",
    "compare",
    "comparison",
    "versus",
    " vs ",
    "correlat",
    "diagnose",
    "investigate",
    "deep dive",
    "deep-dive",
)


class LLMError(Exception):
    """Raised when the OpenRouter call fails or no API key is configured."""


@dataclass
class LLMResponse:
    content: str
    model: str
    tier: str  # "flash" | "pro"
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


def get_config() -> dict:
    return {
        "api_base": os.environ.get("LLM_API_BASE", DEFAULT_API_BASE).rstrip("/"),
        "api_key": os.environ.get("LLM_API_KEY", "").strip(),
        "model_flash": os.environ.get("LLM_MODEL_BI_FLASH", _DEFAULT_FLASH),
        "model_pro": os.environ.get("LLM_MODEL_BI_PRO", _DEFAULT_PRO),
        # Model for the proactive AI CFO report (heavier, narrative-focused).
        "model_cfo": os.environ.get("LLM_MODEL_CFO", _DEFAULT_PRO),
    }


def is_configured() -> bool:
    return bool(get_config()["api_key"])


def pick_tier(question: str) -> str:
    """Heuristic routing: 'flash' by default, 'pro' for deeper questions."""
    text = f" {question.lower()} "
    return "pro" if any(trigger in text for trigger in _PRO_TRIGGERS) else "flash"


def _model_for_tier(tier: str, config: dict) -> str:
    return config["model_pro"] if tier == "pro" else config["model_flash"]


def chat(
    messages: list[dict],
    tier: str = "flash",
    *,
    max_tokens: int = 700,
    temperature: float = 0.2,
    response_format_json: bool = False,
    model: str | None = None,
    reasoning: dict | None = None,
) -> LLMResponse:
    """Single chat completion against OpenRouter.

    Raises ``LLMError`` on failure so the caller can decide whether to escalate
    from Flash to Pro. Pass ``model`` to use an explicit model (e.g. the CFO
    model) instead of the tier-based default; ``tier`` is then only a label.

    ``reasoning`` is forwarded to OpenRouter as-is (e.g. ``{"effort": "low"}``)
    for reasoning models, so their hidden chain-of-thought does not consume the
    whole ``max_tokens`` budget and starve the visible answer.
    """
    config = get_config()
    if not config["api_key"]:
        raise LLMError("No OpenRouter API key found. Set LLM_API_KEY in .env.")

    model = model or _model_for_tier(tier, config)
    payload: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format_json:
        payload["response_format"] = {"type": "json_object"}
    if reasoning is not None:
        payload["reasoning"] = reasoning

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
        # Optional OpenRouter attribution headers.
        "HTTP-Referer": "http://localhost:8501",
        "X-Title": "Fintech Analytics BI Assistant",
    }

    try:
        resp = requests.post(
            f"{config['api_base']}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise LLMError(f"OpenRouter request failed: {exc}") from exc

    if resp.status_code != 200:
        raise LLMError(f"OpenRouter error {resp.status_code}: {resp.text[:400]}")

    data = resp.json()
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected OpenRouter response: {data}") from exc

    # Reasoning models may leave `content` empty and put their text under
    # `reasoning`. That prose is fine for the explainer step, but it is NOT
    # valid JSON, so we must never substitute it when the caller asked for a
    # JSON object — doing so only yields a plan that fails to parse. In that
    # case leave content empty so the caller can retry on another tier.
    content = message.get("content") or ""
    if not content and not response_format_json:
        content = message.get("reasoning") or message.get("reasoning_content") or ""

    usage = data.get("usage", {}) or {}
    return LLMResponse(
        content=content or "",
        model=model,
        tier=tier,
        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
    )
