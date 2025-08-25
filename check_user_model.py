import os
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from models.user import User  # Μην ξεχάσεις να υπάρχει __init__.py στο φάκελο models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"

print("DATABASE_URL:", DATABASE_URL)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Εκτύπωση πεδίων του User μοντέλου
print("User model columns:", User.__table__.columns.keys())

# Έλεγχος αν ο πίνακας users υπάρχει στη βάση
inspector = inspect(engine)
tables = inspector.get_table_names()
print("Tables in DB:", tables)
if 'users' in tables:
    columns = inspector.get_columns('users')
    print("Columns in 'users' table:")
    for col in columns:
        print(f" - {col['name']} ({col['type']})")
else:
    print("No 'users' table found in the database!")

# Φόρτωσε τον χρήστη demo1@test.com και τυπώσε τα πεδία του
user = db.query(User).filter(User.email == "demo1@test.com").first()
if user:
    print("User found before refresh:", dict(user.__dict__))
    db.refresh(user)
    print("User found after refresh:", dict(user.__dict__))
else:
    print("User demo1@test.com not found")

db.close()
