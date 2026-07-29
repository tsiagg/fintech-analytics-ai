-- Fintech simulation — raw relational model (dimensions + facts).
-- Runs automatically on first PostgreSQL init (empty data volume only).

BEGIN;

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS affiliates (
    affiliate_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_code     VARCHAR(8) NOT NULL,
    tier             VARCHAR(32) NOT NULL,
    acquisition_cost NUMERIC(18, 4) NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    user_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    signup_date    DATE NOT NULL,
    country_code   VARCHAR(8) NOT NULL,
    vip_status     VARCHAR(32),
    affiliate_id   BIGINT REFERENCES affiliates (affiliate_id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_affiliate_id ON users (affiliate_id);
CREATE INDEX IF NOT EXISTS idx_users_signup_date ON users (signup_date);

-- ---------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------
-- trades.volume_lots: position size in standard lots (dbt converts to notional USD).
-- trades.pnl: realized P/L in account currency (negative = loss, positive = profit).

CREATE TABLE IF NOT EXISTS trades (
    trade_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users (user_id),
    symbol      VARCHAR(32) NOT NULL,
    volume_lots NUMERIC(18, 4) NOT NULL,
    pnl         NUMERIC(18, 4) NOT NULL,
    trade_ts    TIMESTAMPTZ NOT NULL,
    batch_date  DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades (user_id);
CREATE INDEX IF NOT EXISTS idx_trades_trade_ts ON trades (trade_ts);
CREATE INDEX IF NOT EXISTS idx_trades_batch_date ON trades (batch_date);

CREATE TABLE IF NOT EXISTS deposits (
    deposit_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users (user_id),
    amount           NUMERIC(18, 4) NOT NULL,
    status           VARCHAR(32) NOT NULL,
    payment_provider VARCHAR(64) NOT NULL,
    deposit_ts       TIMESTAMPTZ NOT NULL,
    batch_date       DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deposits_user_id ON deposits (user_id);
CREATE INDEX IF NOT EXISTS idx_deposits_deposit_ts ON deposits (deposit_ts);
CREATE INDEX IF NOT EXISTS idx_deposits_batch_date ON deposits (batch_date);

CREATE TABLE IF NOT EXISTS withdrawals (
    withdrawal_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id          BIGINT NOT NULL REFERENCES users (user_id),
    amount           NUMERIC(18, 4) NOT NULL,
    status           VARCHAR(32) NOT NULL,
    payment_provider VARCHAR(64) NOT NULL,
    withdrawal_ts    TIMESTAMPTZ NOT NULL,
    batch_date       DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_withdrawals_user_id ON withdrawals (user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawals_withdrawal_ts ON withdrawals (withdrawal_ts);
CREATE INDEX IF NOT EXISTS idx_withdrawals_batch_date ON withdrawals (batch_date);

COMMIT;
