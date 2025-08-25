from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2dc41dd3d68"
down_revision = ("36317d8f02b3", "5c12beb4fbaf")
branch_labels = None
depends_on = None

def upgrade():
    # Merge revision – no schema changes
    pass

def downgrade():
    # Merge revision – no schema changes
    pass
