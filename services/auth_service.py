# ---------------------------
# Auth Service (User)
# ---------------------------

from db.database import SessionLocal
from db.models.user import User


# ---------------------------
# Get or Create User
# ---------------------------
def get_or_create_user(email=None, phone=None, name=None):

    db = SessionLocal()

    try:
        # ---------------------------
        # Find user
        # ---------------------------
        if email:
            user = db.query(User).filter(User.email == email).first()
        elif phone:
            user = db.query(User).filter(User.phone == phone).first()
        else:
            return None

        # ---------------------------
        # Create user
        # ---------------------------
        if not user:
            user = User(
                email=email,
                phone=phone,
                name=name
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        else:
            # 🔥 update name propre
            if name and not user.name:
                user.name = name
                db.commit()
                db.refresh(user)  # ✅ IMPORTANT

        # 🔥 détacher proprement APRÈS tout
        db.expunge(user)

        return user

    finally:
        db.close()