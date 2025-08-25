"""add caption to posts

Revision ID: 5c12beb4fbaf
Revises: 0e2cdf803cca
Create Date: 2025-08-21 10:56:43.547689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c12beb4fbaf'
down_revision: Union[str, Sequence[str], None] = '0e2cdf803cca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
