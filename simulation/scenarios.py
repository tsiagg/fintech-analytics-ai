from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class ScenarioParameters:
    id: str
    label: str
    description: str
    new_users_mean: float
    trades_per_active_user_mean: float
    volume_scale: float
    pnl_volatility_multiplier: float
    pnl_mean_drift: float
    deposit_day_probability: float
    withdrawal_day_probability: float
    vip_volume_boost: float
    # User lifecycle (simulation-only; not stored on users table).
    never_churn_fraction: float
    min_tenure_days: int
    max_tenure_days: int
    tenure_scale: float
    vip_tenure_multiplier: float


SCENARIOS: dict[str, ScenarioParameters] = {
    "stable_market": ScenarioParameters(
        id="stable_market",
        label="Stable market",
        description="Balanced flows, moderate activity; clients lose ~60% of trades.",
        new_users_mean=45.0,
        trades_per_active_user_mean=2.2,
        volume_scale=1.0,
        pnl_volatility_multiplier=1.0,
        pnl_mean_drift=-37.5,
        deposit_day_probability=0.12,
        withdrawal_day_probability=0.05,
        vip_volume_boost=1.35,
        never_churn_fraction=0.45,
        min_tenure_days=14,
        max_tenure_days=120,
        tenure_scale=1.0,
        vip_tenure_multiplier=1.35,
    ),
    "high_volatility": ScenarioParameters(
        id="high_volatility",
        label="High volatility",
        description="Heavy trading and wider PnL; withdrawals rise.",
        new_users_mean=38.0,
        trades_per_active_user_mean=4.5,
        volume_scale=1.65,
        pnl_volatility_multiplier=1.4,
        pnl_mean_drift=-37.5,
        deposit_day_probability=0.16,
        withdrawal_day_probability=0.12,
        vip_volume_boost=1.45,
        never_churn_fraction=0.42,
        min_tenure_days=10,
        max_tenure_days=100,
        tenure_scale=0.88,
        vip_tenure_multiplier=1.3,
    ),
    "market_crash": ScenarioParameters(
        id="market_crash",
        label="Market crash",
        description="Fewer signups; negative PnL bias; more withdrawals.",
        new_users_mean=22.0,
        trades_per_active_user_mean=3.2,
        volume_scale=1.65,
        pnl_volatility_multiplier=2.4,
        pnl_mean_drift=-87.5,
        deposit_day_probability=0.06,
        withdrawal_day_probability=0.18,
        vip_volume_boost=1.2,
        never_churn_fraction=0.38,
        min_tenure_days=7,
        max_tenure_days=90,
        tenure_scale=0.72,
        vip_tenure_multiplier=1.25,
    ),
    "marketing_campaign": ScenarioParameters(
        id="marketing_campaign",
        label="Marketing campaign",
        description="Strong signups and deposits.",
        new_users_mean=95.0,
        trades_per_active_user_mean=1.9,
        volume_scale=1.2,
        pnl_volatility_multiplier=1.1,
        pnl_mean_drift=0.0,
        deposit_day_probability=0.22,
        withdrawal_day_probability=0.04,
        vip_volume_boost=1.4,
        never_churn_fraction=0.52,
        min_tenure_days=21,
        max_tenure_days=150,
        tenure_scale=1.15,
        vip_tenure_multiplier=1.45,
    ),
    "technical_problem": ScenarioParameters(
        id="technical_problem",
        label="Technical problem",
        description="Platform outage: no signups, minimal trading, low PnL, elevated churn.",
        new_users_mean=0.0,
        trades_per_active_user_mean=0.25,
        volume_scale=0.30,
        pnl_volatility_multiplier=0.45,
        pnl_mean_drift=0.0,
        deposit_day_probability=0.02,
        withdrawal_day_probability=0.06,
        vip_volume_boost=1.0,
        never_churn_fraction=0.22,
        min_tenure_days=5,
        max_tenure_days=60,
        tenure_scale=0.55,
        vip_tenure_multiplier=1.1,
    ),
    "holiday_lull": ScenarioParameters(
        id="holiday_lull",
        label="Holiday lull",
        description="Seasonal quiet: lower activity, neutral PnL, softer cash flows.",
        new_users_mean=28.0,
        trades_per_active_user_mean=1.4,
        volume_scale=0.75,
        pnl_volatility_multiplier=0.85,
        pnl_mean_drift=-37.5,
        deposit_day_probability=0.08,
        withdrawal_day_probability=0.04,
        vip_volume_boost=1.2,
        never_churn_fraction=0.40,
        min_tenure_days=12,
        max_tenure_days=110,
        tenure_scale=0.92,
        vip_tenure_multiplier=1.25,
    ),
}


# Calendar-fixed scenarios (month, day) — repeats every year; not in DEFAULT_SCENARIO_WEIGHTS.
FIXED_HOLIDAY_SCENARIOS: dict[tuple[int, int], str] = {
    (1, 1): "holiday_lull",   # New Year's Day
    (7, 4): "holiday_lull",   # US Independence Day
    (12, 25): "holiday_lull",  # Christmas Day
}


# Daily scenario draw when no override (must sum to 1.0).
DEFAULT_SCENARIO_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("stable_market", 0.43),
    ("marketing_campaign", 0.30),
    ("high_volatility", 0.23),
    ("market_crash", 0.02),
    ("technical_problem", 0.02),
)


def pick_scenario_for_day(
    batch_date: date,
    rng: random.Random,
    scenario_override: str | None,
) -> ScenarioParameters:
    if scenario_override:
        return get_scenario(scenario_override)
    holiday_id = FIXED_HOLIDAY_SCENARIOS.get((batch_date.month, batch_date.day))
    if holiday_id is not None:
        return get_scenario(holiday_id)
    ids, weights = zip(*DEFAULT_SCENARIO_WEIGHTS)
    chosen = rng.choices(list(ids), weights=list(weights), k=1)[0]
    return get_scenario(chosen)


def get_scenario(scenario_id: str) -> ScenarioParameters:
    key = scenario_id.strip().lower().replace("-", "_")
    if key not in SCENARIOS:
        known = ", ".join(sorted(SCENARIOS))
        raise ValueError(f"Unknown scenario '{scenario_id}'. Known: {known}")
    return SCENARIOS[key]


def documented_scenarios() -> list[dict]:
    return [
        {
            "id": s.id,
            "label": s.label,
            "description": s.description,
            "new_users_mean": s.new_users_mean,
            "trades_per_active_user_mean": s.trades_per_active_user_mean,
            "volume_scale": s.volume_scale,
            "pnl_volatility_multiplier": s.pnl_volatility_multiplier,
            "pnl_mean_drift": s.pnl_mean_drift,
            "deposit_day_probability": s.deposit_day_probability,
            "withdrawal_day_probability": s.withdrawal_day_probability,
            "vip_volume_boost": s.vip_volume_boost,
            "never_churn_fraction": s.never_churn_fraction,
            "min_tenure_days": s.min_tenure_days,
            "max_tenure_days": s.max_tenure_days,
            "tenure_scale": s.tenure_scale,
            "vip_tenure_multiplier": s.vip_tenure_multiplier,
        }
        for s in SCENARIOS.values()
    ]
