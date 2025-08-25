from models.user import User
from database import SessionLocal

def main():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "demo1@test.com").first()
        if not user:
            print("User not found")
            return
        
        print("User found before refresh:", user.__dict__)
        
        db.refresh(user)  # Εξαναγκάζουμε ανανέωση από βάση
        
        print("User found after refresh:", user.__dict__)
        print("sync_url after refresh:", getattr(user, 'sync_url', None))
    finally:
        db.close()

if __name__ == "__main__":
    main()
