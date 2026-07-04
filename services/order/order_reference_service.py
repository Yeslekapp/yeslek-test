# ---------------------------
# Feature: Order Reference Service
# ---------------------------

from sqlalchemy import text

from db.database import SessionLocal


class OrderReferenceService:

    # ---------------------------
    # Generate sequential reference
    # ---------------------------
    @staticmethod
    def generate_order_reference() -> str:

        db = SessionLocal()

        try:
            result = db.execute(
                text(
                    "SELECT nextval('yeslek_order_ref_seq')"
                )
            )

            number = result.scalar()

            return f"{int(number):09d}"

        finally:
            db.close()