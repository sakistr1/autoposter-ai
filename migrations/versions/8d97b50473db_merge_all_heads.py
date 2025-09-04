"""merge ALL heads

Revision ID: 8d97b50473db
Revises: 2dc41dd3d68, f43381c4b5e9
Create Date: 2025-08-23 11:15:55.258964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d97b50473db'
down_revision: Union[str, Sequence[str], None] = ('2dc41dd3d68', 'f43381c4b5e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
