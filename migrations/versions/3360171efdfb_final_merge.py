"""final merge

Revision ID: 3360171efdfb
Revises: 8235a5a7499b, a3a99caac34d
Create Date: 2025-08-23 11:53:18.568251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3360171efdfb'
down_revision: Union[str, Sequence[str], None] = ('8235a5a7499b', 'a3a99caac34d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
