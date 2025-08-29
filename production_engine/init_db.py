"""
ΤΡΕΞΙΜΟ:
    cd ~/autoposter-ai
    python -m production_engine.init_db
"""

from production_engine.engine_database import Base, engine

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("[production_engine] Database initialized (engine.db).")
