import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Βασικός φάκελος backend
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Σωστό path για τη βάση δεδομένων SQLite
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Απαραίτητο για SQLite με FastAPI και SQLAlchemy
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency για να παίρνουμε τη DB session στα FastAPI endpoints
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
