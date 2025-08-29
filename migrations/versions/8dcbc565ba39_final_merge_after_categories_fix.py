"""final merge after categories fix

Revision ID: 8dcbc565ba39
Revises: 1861823fd513
Create Date: 2025-08-23 13:04:54.137145

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8dcbc565ba39'
down_revision: Union[str, Sequence[str], None] = '1861823fd513'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
