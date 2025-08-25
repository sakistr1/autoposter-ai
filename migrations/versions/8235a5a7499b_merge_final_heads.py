"""merge final heads

Revision ID: 8235a5a7499b
Revises: 8d97b50473db
Create Date: 2025-08-23 11:44:53.039813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8235a5a7499b'
down_revision: Union[str, Sequence[str], None] = '8d97b50473db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
