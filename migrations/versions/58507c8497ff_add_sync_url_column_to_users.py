"""add sync_url column to users (idempotent)"""

from alembic import op
import sqlalchemy as sa

revision = "58507c8497ff"
down_revision = "e260de4fc7ad"
branch_labels = None
depends_on = None

def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return False
    return col in cols

def upgrade():
    if not _has_col("users", "sync_url"):
        with op.batch_alter_table("users") as b:
            b.add_column(sa.Column("sync_url", sa.String(), nullable=True))

def downgrade():
    if _has_col("users", "sync_url"):
        with op.batch_alter_table("users") as b:
            b.drop_column("sync_url")
