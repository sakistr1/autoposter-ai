from database import SessionLocal
from models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

email = "admin@example.com"
password = "admin1234"
hashed_password = pwd_context.hash(password)

existing = db.query(User).filter(User.email == email).first()
if existing:
    print("❌ Ο χρήστης υπάρχει ήδη.")
else:
    new_user = User(email=email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    print("✅ Ο admin χρήστης δημιουργήθηκε με επιτυχία.")
