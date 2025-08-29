from __future__ import annotations
import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Βάλε το project root στο PYTHONPATH ώστε να δουλέψουν τα imports ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../autoposter-ai
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Φόρτωσε alembic.ini ---
config = context.config

# --- Πάρε DB URL από env και πέρασέ το στο Alembic ---
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# --- Logging του Alembic ---
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Προσπάθησε να βρεις το Base από διάφορα πιθανά modules ---
Base = None
errors = []
for modpath in [
    "database",          # συνήθως: database.py με Base = declarative_base()
    "models",            # αν έχεις models/__init__.py με Base
    "models.base",       # αν έχεις models/base.py με Base
    "db",                # εναλλακτικά
]:
    try:
        mod = __import__(modpath, fromlist=["Base"])
        Base = getattr(mod, "Base", None)
        if Base is not None:
            break
    except Exception as e:
        errors.append(f"{modpath}: {e}")

if Base is None:
    raise RuntimeError(
        "Alembic: Δεν βρέθηκε Base. Δοκίμασα: "
        + ", ".join(errors)
        + "\nΒεβαιώσου ότι κάπου έχεις `Base = declarative_base()` "
          "και προσαρμόσε το import εδώ."
    )

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
