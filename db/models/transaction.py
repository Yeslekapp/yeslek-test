# ---------------------------
# Transaction Model (PRO SAFE)
# ---------------------------

from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean
from db.database import Base
from datetime import datetime


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, nullable=False, index=True)

    reference = Column(String, unique=True, nullable=False, index=True)

    phone = Column(String, nullable=False)
    country_iso = Column(String)

    amount = Column(Numeric(10, 2), nullable=False)

    # ---------------------------
    # Reloadly
    # ---------------------------
    plan_id = Column(Integer)
    operator_id = Column(Integer)
    reloadly_transaction_id = Column(Integer, index=True)

    # ---------------------------
    # Stripe payment
    # ---------------------------
    stripe_id = Column(String, index=True)
    payment_intent_id = Column(String, index=True)
    stripe_customer_id = Column(String, index=True)
    payment_method_id = Column(String)

    payment_method = Column(String)
    payment_channel = Column(String)

    # ---------------------------
    # Amounts / fees
    # ---------------------------
    base_amount = Column(Numeric(10, 2), default=0)
    charged_amount = Column(Numeric(10, 2), default=0)
    fee = Column(Numeric(10, 2), default=0)
    tax = Column(Numeric(10, 2), default=0)
    total = Column(Numeric(10, 2), default=0)

    # ---------------------------
    # Saved card display
    # ---------------------------
    card_brand = Column(String)
    card_last4 = Column(String)
    card_expiry = Column(String)

    # ---------------------------
    # Admin tracking
    # ---------------------------
    admin_received = Column(Boolean, default=False)

    status = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )