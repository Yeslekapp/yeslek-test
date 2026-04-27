# ---------------------------
# User Service (POSTGRES FINAL)
# ---------------------------

from db.database import SessionLocal
from db.models.user import User


class UserService:

    # ---------------------------
    # Get user
    # ---------------------------
    @staticmethod
    def get_by_id(user_id):

        if not user_id:
            return None

        db = SessionLocal()

        return db.query(User).filter(
            User.id == user_id
        ).first()

    # ---------------------------
    # Get balance
    # ---------------------------
    @staticmethod
    def get_balance(user_id):

        db = SessionLocal()

        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            return 0.0

        return float(user.balance or 0.0)

    # ---------------------------
    # Add balance
    # ---------------------------
    @staticmethod
    def add_balance(user_id, amount):

        db = SessionLocal()

        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            return

        user.balance = float(user.balance or 0) + float(amount)

        db.commit()

    # ---------------------------
    # Update name
    # ---------------------------
    @staticmethod
    def update(user_id, name=None):

        db = SessionLocal()

        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            return

        if name:
            user.name = name

        db.commit()

    # ---------------------------
    # Update avatar
    # ---------------------------
    @staticmethod
    def update_avatar(user_id, avatar_url):

        db = SessionLocal()

        user = db.query(User).filter(
            User.id == user_id
        ).first()

        if not user:
            return

        user.avatar = avatar_url

        db.commit()

    # ---------------------------
    # Get all users (ADMIN)
    # ---------------------------
    @staticmethod
    def get_all():

        db = SessionLocal()

        users = db.query(User).all()

        result = []

        for u in users:
            result.append({
                "user_id": u.id,
                "email": u.email,
                "name": u.name,
            })

        return result