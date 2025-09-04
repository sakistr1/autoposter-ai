# check_sync_url.py
from database import SessionLocal
from models import User

db = SessionLocal()
users = db.query(User).all()

for user in users:
    print(f"Username: {user.username}")
    print(f"Email: {user.email}")
    print(f"sync_url: {user.sync_url}")
    print("------")
