"""final merge after categories/templates fixes

Revision ID: 5e94eb03c8c4
Revises: 8dcbc565ba39
Create Date: 2025-08-23 13:13:13.145892

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e94eb03c8c4'
down_revision: Union[str, Sequence[str], None] = '8dcbc565ba39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
