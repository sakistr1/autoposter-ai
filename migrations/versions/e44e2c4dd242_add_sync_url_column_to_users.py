"""add sync_url (idempotent)"""

from alembic import op
import sqlalchemy as sa

revision = "e44e2c4dd242"
down_revision = "e260de4fc7ad"
branch_labels = None
depends_on = None

def _has_col(table, col):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        return any(c["name"] == col for c in insp.get_columns(table))
    except Exception:
        return False

def upgrade():
    if not _has_col("users", "sync_url"):
        with op.batch_alter_table("users") as b:
            b.add_column(sa.Column("sync_url", sa.String(), nullable=True))

def downgrade():
    if _has_col("users", "sync_url"):
        with op.batch_alter_table("users") as b:
            b.drop_column("sync_url")
