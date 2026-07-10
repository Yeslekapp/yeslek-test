-- ---------------------------
-- Feature: Ensure saved cards columns
-- ---------------------------

ALTER TABLE saved_cards
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
ADD COLUMN IF NOT EXISTS payment_method_id TEXT,
ADD COLUMN IF NOT EXISTS brand TEXT DEFAULT 'card',
ADD COLUMN IF NOT EXISTS last4 TEXT,
ADD COLUMN IF NOT EXISTS exp_month INTEGER,
ADD COLUMN IF NOT EXISTS exp_year INTEGER,
ADD COLUMN IF NOT EXISTS expiry TEXT,
ADD COLUMN IF NOT EXISTS fingerprint TEXT,
ADD COLUMN IF NOT EXISTS is_default BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_saved_cards_user_id
ON saved_cards(user_id);

CREATE INDEX IF NOT EXISTS idx_saved_cards_user_active
ON saved_cards(user_id, deleted_at);

CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_cards_payment_method_id
ON saved_cards(payment_method_id)
WHERE payment_method_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_saved_cards_user_fingerprint_active
ON saved_cards(user_id, fingerprint)
WHERE fingerprint IS NOT NULL AND deleted_at IS NULL;


-- ---------------------------
-- Feature: Ensure transaction payment columns
-- ---------------------------

ALTER TABLE transactions
ADD COLUMN IF NOT EXISTS reloadly_transaction_id INTEGER,
ADD COLUMN IF NOT EXISTS stripe_id TEXT,
ADD COLUMN IF NOT EXISTS payment_intent_id TEXT,
ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
ADD COLUMN IF NOT EXISTS payment_method_id TEXT,
ADD COLUMN IF NOT EXISTS payment_method TEXT,
ADD COLUMN IF NOT EXISTS payment_channel TEXT,
ADD COLUMN IF NOT EXISTS base_amount NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS charged_amount NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS fee NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS tax NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS total NUMERIC(10, 2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS card_brand TEXT,
ADD COLUMN IF NOT EXISTS card_last4 TEXT,
ADD COLUMN IF NOT EXISTS card_expiry TEXT,
ADD COLUMN IF NOT EXISTS admin_received BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_transactions_stripe_id
ON transactions(stripe_id);

CREATE INDEX IF NOT EXISTS idx_transactions_payment_intent_id
ON transactions(payment_intent_id);

CREATE INDEX IF NOT EXISTS idx_transactions_stripe_customer_id
ON transactions(stripe_customer_id);

CREATE INDEX IF NOT EXISTS idx_transactions_reloadly_transaction_id
ON transactions(reloadly_transaction_id);