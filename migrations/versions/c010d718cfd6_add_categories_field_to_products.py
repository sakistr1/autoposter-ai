"""Add categories field to products (idempotent)"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = "c010d718cfd6"
down_revision = "58507c8497ff"
branch_labels = None
depends_on = None

def _has_col(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
        return col in cols
    except Exception:
        return False

def upgrade() -> None:
    if not _has_col("products", "categories"):
        with op.batch_alter_table("products") as b:
            b.add_column(sa.Column("categories", sa.String(), nullable=True))

def downgrade() -> None:
    if _has_col("products", "categories"):
        with op.batch_alter_table("products") as b:
            b.drop_column("categories")
