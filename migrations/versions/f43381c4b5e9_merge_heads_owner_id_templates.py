"""merge heads owner_id templates

Revision ID: f43381c4b5e9
Revises: a7f6dc5abdbb, bd49ce089f62
Create Date: 2025-08-23 11:14:23.843454

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f43381c4b5e9'
down_revision: Union[str, Sequence[str], None] = ('a7f6dc5abdbb', 'bd49ce089f62')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
