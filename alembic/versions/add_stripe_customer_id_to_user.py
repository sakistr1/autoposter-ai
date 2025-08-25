"""add stripe_customer_id to user"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_stripe_customer_id_to_user'
down_revision = '98ee19248936'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(), nullable=True))

def downgrade():
    op.drop_column('users', 'stripe_customer_id')
