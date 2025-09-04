"""merge heads

Revision ID: ef2259a67b93
Revises: 63babc381c46, c010d718cfd6
Create Date: 2025-07-26 18:05:59.694157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef2259a67b93'
down_revision: Union[str, Sequence[str], None] = ('63babc381c46', 'c010d718cfd6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
