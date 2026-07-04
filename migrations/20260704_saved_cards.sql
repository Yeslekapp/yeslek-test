-- ---------------------------
-- Feature: Saved cards PostgreSQL
-- ---------------------------

CREATE TABLE IF NOT EXISTS stripe_customers (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    email TEXT,
    stripe_customer_id TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_cards (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    stripe_customer_id TEXT NOT NULL,
    payment_method_id TEXT NOT NULL UNIQUE,
    brand TEXT NOT NULL DEFAULT 'card',
    last4 TEXT NOT NULL,
    exp_month INTEGER NOT NULL,
    exp_year INTEGER NOT NULL,
    expiry TEXT NOT NULL,
    fingerprint TEXT,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_saved_cards_user_id
ON saved_cards(user_id);

CREATE INDEX IF NOT EXISTS idx_saved_cards_user_active
ON saved_cards(user_id, deleted_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_cards_user_fingerprint_active
ON saved_cards(user_id, fingerprint)
WHERE fingerprint IS NOT NULL AND deleted_at IS NULL;