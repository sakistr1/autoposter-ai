# test_user_sync_url.py
from database import SessionLocal
from models.user import User

def main():
    db = SessionLocal()
    try:
        print("Columns in User model:", User.__table__.columns.keys())

        user = db.query(User).filter(User.email == "demo1@test.com").first()
        if not user:
            print("User not found")
            return

        print("User found before refresh:", user.__dict__)
        db.refresh(user)
        print("User found after refresh:", user.__dict__)

        # Προσπαθούμε να πάρουμε το sync_url, αν δεν υπάρχει θα δείξει None
        print("sync_url after refresh:", getattr(user, "sync_url", None))
    finally:
        db.close()

if __name__ == "__main__":
    main()
