"""Add categories field to products (NO-OP / idempotent)"""

from alembic import op
import sqlalchemy as sa

# Alembic identifiers
revision = "63babc381c46"
down_revision = "58507c8497ff"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # NO-OP: η στήλη υπάρχει ήδη
    pass

def downgrade() -> None:
    # NO-OP
    pass
