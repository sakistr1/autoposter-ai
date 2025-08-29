from database import SessionLocal
from models import User
from passlib.hash import bcrypt

db = SessionLocal()

# Έλεγξε αν υπάρχει ήδη ο admin
existing = db.query(User).filter(User.username == "admin").first()

if existing:
    print("❗ Ο χρήστης admin υπάρχει ήδη.")
else:
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=bcrypt.hash("admin123"),
        sync_url="http://127.0.0.1:9000/mock-products"  # βάλε εδώ ό,τι URL θες
    )
    db.add(user)
    db.commit()
    print("✅ Admin user created!")
