from __future__ import annotations

import hashlib
import logging
import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Sequence

import psycopg2
from psycopg2.extras import execute_batch

from simulation.scenarios import ScenarioParameters, pick_scenario_for_day
from simulation.settings import postgres_dsn_parts

logger = logging.getLogger(__name__)

SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD", "XAUUSD")
USER_COUNTRY_CODES = ("US", "GB", "DE", "FR", "ES", "IT", "NL", "AU", "SG", "AE", "JP")
PAYMENT_PROVIDERS = ("stripe", "adyen", "paypal", "bank_transfer")

# Standard lot sizes per instrument (retail-weighted; dbt converts lots → notional USD).
SYMBOL_LOT_CHOICES: dict[str, tuple[tuple[float, float], ...]] = {
    "EURUSD": ((0.01, 28), (0.1, 32), (0.5, 22), (1.0, 12), (2.0, 5), (5.0, 1)),
    "GBPUSD": ((0.01, 28), (0.1, 32), (0.5, 22), (1.0, 12), (2.0, 5), (5.0, 1)),
    "USDJPY": ((0.01, 26), (0.1, 30), (0.5, 24), (1.0, 14), (3.0, 5), (5.0, 1)),
    "BTCUSD": ((0.01, 35), (0.05, 28), (0.1, 22), (0.25, 10), (0.5, 4), (1.0, 1)),
    "ETHUSD": ((0.01, 32), (0.05, 30), (0.1, 24), (0.5, 10), (1.0, 3), (2.0, 1)),
    "XAUUSD": ((0.01, 22), (0.1, 30), (0.5, 26), (1.0, 16), (2.0, 5), (5.0, 1)),
}
VIP_FRACTION = 0.06
AFFILIATE_ATTRIBUTION_FRACTION = 0.72

# Deterministic per-user lifecycle (not persisted; recomputed from user_id + signup_date).
LIFECYCLE_SALT = "fintech-sim-lifecycle-v1"
LAST_ACTIVE_FAR_FUTURE = date(2099, 12, 31)

AFFILIATE_BLUEPRINT: tuple[tuple[str, str, float], ...] = (
    ("DE", "tier_a", 420.0),
    ("DE", "tier_b", 310.0),
    ("US", "tier_a", 455.0),
    ("US", "tier_b", 280.0),
    ("AU", "tier_a", 390.0),
    ("AU", "tier_b", 265.0),
)


def _seed_from(batch_date: date, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    return batch_date.toordinal() * 1_000_003 + 42_001


def _random_ts(rng: random.Random, batch_date: date) -> datetime:
    base = datetime(batch_date.year, batch_date.month, batch_date.day, tzinfo=timezone.utc)
    return base + timedelta(seconds=rng.randint(0, 86_399))


def _pick_weighted_status(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.87:
        return "completed"
    if r < 0.95:
        return "pending"
    return "failed"


def _ensure_affiliates(cur) -> None:
    cur.execute("SELECT COUNT(*) FROM affiliates")
    (n,) = cur.fetchone()
    if n > 0:
        return
    rows = [(cc, tier, cost) for cc, tier, cost in AFFILIATE_BLUEPRINT]
    execute_batch(
        cur,
        "INSERT INTO affiliates (country_code, tier, acquisition_cost) VALUES (%s,%s,%s)",
        rows,
    )
    logger.info("Seeded %s affiliates", len(rows))


def _fetch_affiliate_ids(cur) -> Sequence[int]:
    cur.execute("SELECT affiliate_id FROM affiliates ORDER BY affiliate_id")
    return [row[0] for row in cur.fetchall()]


def _idempotent_scrub_batch(cur, batch_date: date) -> None:
    cur.execute("DELETE FROM withdrawals WHERE batch_date = %s", (batch_date,))
    cur.execute("DELETE FROM deposits WHERE batch_date = %s", (batch_date,))
    cur.execute("DELETE FROM trades WHERE batch_date = %s", (batch_date,))
    # Only remove signup-day users with no remaining facts (avoids FK violations on re-run).
    cur.execute(
        """
        DELETE FROM users u
        WHERE u.signup_date = %s
          AND NOT EXISTS (SELECT 1 FROM trades t WHERE t.user_id = u.user_id)
          AND NOT EXISTS (SELECT 1 FROM deposits d WHERE d.user_id = u.user_id)
          AND NOT EXISTS (SELECT 1 FROM withdrawals w WHERE w.user_id = u.user_id)
        """,
        (batch_date,),
    )


def _poisson(rng: random.Random, lam: float) -> int:
    lam = max(float(lam), 1e-6)
    if lam > 30:
        return max(0, int(rng.gauss(lam, math.sqrt(lam))))
    l_val = math.exp(-lam)
    k = 0
    p = 1.0
    while p > l_val:
        k += 1
        p *= rng.random()
    return k - 1


def _vip_status_for_user(rng: random.Random) -> str | None:
    return "vip" if rng.random() < VIP_FRACTION else None


def _maybe_affiliate_id(rng: random.Random, affiliate_ids: Sequence[int]) -> int | None:
    if not affiliate_ids or rng.random() > AFFILIATE_ATTRIBUTION_FRACTION:
        return None
    return rng.choice(affiliate_ids)


def _lifecycle_digest(user_id: int, signup_date: date) -> bytes:
    payload = f"{user_id}:{signup_date.isoformat()}:{LIFECYCLE_SALT}".encode()
    return hashlib.sha256(payload).digest()


def _last_active_date(
    user_id: int,
    signup_date: date,
    params: ScenarioParameters,
    *,
    is_vip: bool,
) -> date:
    """Last calendar day this user may generate trades/deposits/withdrawals."""
    digest = _lifecycle_digest(user_id, signup_date)
    bucket = int.from_bytes(digest[:4], "big") / 2**32
    if bucket < params.never_churn_fraction:
        return LAST_ACTIVE_FAR_FUTURE

    span = max(0, params.max_tenure_days - params.min_tenure_days)
    tenure_offset = int.from_bytes(digest[4:8], "big") % (span + 1)
    tenure_days = params.min_tenure_days + tenure_offset
    tenure_days = max(params.min_tenure_days, int(tenure_days * params.tenure_scale))
    if is_vip:
        tenure_days = max(params.min_tenure_days, int(tenure_days * params.vip_tenure_multiplier))
    return signup_date + timedelta(days=tenure_days)


def _eligible_users_for_day(
    cohort: Sequence[tuple[int, date, str]],
    batch_date: date,
    params: ScenarioParameters,
) -> list[tuple[int, str]]:
    eligible: list[tuple[int, str]] = []
    for user_id, signup_date, vip_flag in cohort:
        is_vip = vip_flag == "vip"
        if batch_date <= _last_active_date(user_id, signup_date, params, is_vip=is_vip):
            eligible.append((user_id, vip_flag))
    return eligible


def _sample_volume_lots(
    rng: random.Random,
    symbol: str,
    params: ScenarioParameters,
    *,
    is_vip: bool,
) -> float:
    spec = SYMBOL_LOT_CHOICES[symbol]
    lots, weights = zip(*spec)
    weight_list = list(weights)
    if is_vip:
        weight_list = [w * (1.0 + i * 0.12) for i, w in enumerate(weight_list)]
    chosen = rng.choices(list(lots), weights=weight_list, k=1)[0]
    scaled = chosen * params.volume_scale
    if is_vip:
        scaled *= 1.15
    return round(scaled, 4)


def _sample_trade_pnl(
    rng: random.Random,
    volume_lots: float,
    params: ScenarioParameters,
) -> float:
    magnitude = abs(rng.gauss(0.0, 72.0 * params.pnl_volatility_multiplier))
    magnitude += abs(params.pnl_mean_drift) * 0.15
    win_prob = 0.5 + max(-0.4, min(0.4, params.pnl_mean_drift / 250.0))
    sign = 1 if rng.random() < win_prob else -1
    pnl = round(sign * magnitude * max(volume_lots, 0.01) * 12.0, 4)
    if pnl == 0:
        pnl = round(sign * 0.01, 4)
    return pnl


def run_daily_batch(
    batch_date: date,
    *,
    scenario: str | None = None,
    seed: int | None = None,
) -> dict:
    rng = random.Random(_seed_from(batch_date, seed))
    params = pick_scenario_for_day(batch_date, rng, scenario)
    cfg = postgres_dsn_parts()

    summary: dict = {"batch_date": batch_date.isoformat(), "scenario_id": params.id}

    with psycopg2.connect(**cfg) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            _ensure_affiliates(cur)
            affiliate_ids = _fetch_affiliate_ids(cur)

            _idempotent_scrub_batch(cur, batch_date)

            new_users = _poisson(rng, params.new_users_mean)
            user_rows: list[tuple] = []
            for _ in range(new_users):
                cc = rng.choice(USER_COUNTRY_CODES)
                user_rows.append(
                    (
                        batch_date,
                        cc,
                        _vip_status_for_user(rng),
                        _maybe_affiliate_id(rng, affiliate_ids),
                    )
                )

            if user_rows:
                execute_batch(
                    cur,
                    "INSERT INTO users (signup_date, country_code, vip_status, affiliate_id) "
                    "VALUES (%s,%s,%s,%s)",
                    user_rows,
                    page_size=500,
                )

            cur.execute(
                "SELECT user_id, signup_date, COALESCE(vip_status, '') "
                "FROM users WHERE signup_date <= %s ORDER BY user_id",
                (batch_date,),
            )
            cohort = [(int(r[0]), r[1], str(r[2])) for r in cur.fetchall()]
            active = _eligible_users_for_day(cohort, batch_date, params)

            summary["cohort_users"] = len(cohort)
            summary["eligible_users"] = len(active)
            summary["active_users"] = len(active)
            summary["churned_skipped_users"] = len(cohort) - len(active)
            summary["new_users"] = new_users

            trade_rows: list[tuple] = []
            for user_id, vip_flag in active:
                is_vip = vip_flag == "vip"
                lam = (
                    params.trades_per_active_user_mean
                    * params.volume_scale
                    * (params.vip_volume_boost if is_vip else 1.0)
                )
                for _ in range(_poisson(rng, lam)):
                    symbol = rng.choice(SYMBOLS)
                    volume_lots = _sample_volume_lots(rng, symbol, params, is_vip=is_vip)
                    pnl = _sample_trade_pnl(rng, volume_lots, params)
                    trade_rows.append(
                        (user_id, symbol, volume_lots, pnl, _random_ts(rng, batch_date), batch_date),
                    )

            if trade_rows:
                execute_batch(
                    cur,
                    "INSERT INTO trades (user_id, symbol, volume_lots, pnl, trade_ts, batch_date) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    trade_rows,
                    page_size=500,
                )

            deposit_rows: list[tuple] = []
            withdrawal_rows: list[tuple] = []
            for user_id, vip_flag in active:
                is_vip = vip_flag == "vip"
                if rng.random() < params.deposit_day_probability:
                    amt = round(
                        rng.lognormvariate(3.2, 0.45) * (1.2 if is_vip else 1.0),
                        4,
                    )
                    deposit_rows.append(
                        (
                            user_id,
                            amt,
                            _pick_weighted_status(rng),
                            rng.choice(PAYMENT_PROVIDERS),
                            _random_ts(rng, batch_date),
                            batch_date,
                        ),
                    )
                if rng.random() < params.withdrawal_day_probability:
                    amt = round(
                        rng.lognormvariate(2.9, 0.5) * (1.05 if is_vip else 1.0),
                        4,
                    )
                    withdrawal_rows.append(
                        (
                            user_id,
                            amt,
                            _pick_weighted_status(rng),
                            rng.choice(PAYMENT_PROVIDERS),
                            _random_ts(rng, batch_date),
                            batch_date,
                        ),
                    )

            if deposit_rows:
                execute_batch(
                    cur,
                    "INSERT INTO deposits (user_id, amount, status, payment_provider, deposit_ts, batch_date) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    deposit_rows,
                    page_size=500,
                )
            if withdrawal_rows:
                execute_batch(
                    cur,
                    "INSERT INTO withdrawals (user_id, amount, status, payment_provider, withdrawal_ts, batch_date) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    withdrawal_rows,
                    page_size=500,
                )

            conn.commit()

            summary["trades"] = len(trade_rows)
            summary["deposits"] = len(deposit_rows)
            summary["withdrawals"] = len(withdrawal_rows)

    logger.info("Batch %s scenario=%s %s", batch_date, params.id, summary)
    return summary


def run_daily_batch_iso(date_str: str, *, scenario: str | None = None, seed: int | None = None) -> dict:
    parts = date_str.strip().split("-", 2)
    if len(parts) != 3:
        raise ValueError(f"Expected YYYY-MM-DD, got {date_str!r}")
    y, m, d = (int(parts[0]), int(parts[1]), int(parts[2]))
    return run_daily_batch(date(y, m, d), scenario=scenario, seed=seed)
