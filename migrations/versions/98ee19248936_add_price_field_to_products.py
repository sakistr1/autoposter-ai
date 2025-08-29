"""Add price field to products

Revision ID: 98ee19248936
Revises: ef2259a67b93
Create Date: 2025-07-26 18:32:12.418127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98ee19248936'
down_revision: Union[str, Sequence[str], None] = 'ef2259a67b93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('products', sa.Column('price', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('products', 'price')
