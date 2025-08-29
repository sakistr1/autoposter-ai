from database import SessionLocal
from models import User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

admin_email = "admin@example.com"
new_password = "admin1234"

user = db.query(User).filter(User.email == admin_email).first()
if not user:
    print("❌ Ο admin δεν υπάρχει.")
else:
    user.hashed_password = pwd_context.hash(new_password)
    db.commit()
    print("✅ Ο κωδικός admin άλλαξε επιτυχώς.")
