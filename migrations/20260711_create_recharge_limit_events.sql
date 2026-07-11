-- ---------------------------
-- Feature: Global Recharge Limit
-- ---------------------------

CREATE TABLE IF NOT EXISTS recharge_limit_events (
    id BIGSERIAL PRIMARY KEY,

    phone_key CHAR(64) NOT NULL,

    reservation_key VARCHAR(128) NOT NULL UNIQUE,

    payment_intent_id VARCHAR(255),

    status VARCHAR(20) NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT ck_recharge_limit_events_status
        CHECK (
            status IN (
                'RESERVED',
                'SUCCESS',
                'RELEASED'
            )
        )
);


-- ---------------------------
-- Active phone lookup
-- ---------------------------

CREATE INDEX IF NOT EXISTS idx_recharge_limit_events_active_phone
ON recharge_limit_events (
    phone_key,
    expires_at
)
WHERE status IN (
    'RESERVED',
    'SUCCESS'
);


-- ---------------------------
-- Payment Intent lookup
-- ---------------------------

CREATE INDEX IF NOT EXISTS idx_recharge_limit_events_payment_intent
ON recharge_limit_events (
    payment_intent_id
)
WHERE payment_intent_id IS NOT NULL;