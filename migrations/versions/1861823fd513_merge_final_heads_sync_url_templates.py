"""merge final heads (sync_url + templates)

Revision ID: 1861823fd513
Revises: 3360171efdfb, e44e2c4dd242
Create Date: 2025-08-23 12:49:38.589785

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1861823fd513'
down_revision: Union[str, Sequence[str], None] = ('3360171efdfb', 'e44e2c4dd242')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
