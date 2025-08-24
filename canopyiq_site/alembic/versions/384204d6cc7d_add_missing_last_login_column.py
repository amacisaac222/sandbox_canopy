"""Add missing last_login column

Revision ID: 384204d6cc7d
Revises: 1ec45058bcca
Create Date: 2025-08-20 14:55:35.921466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '384204d6cc7d'
down_revision: Union[str, Sequence[str], None] = '1ec45058bcca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing last_login column to users table
    op.add_column('users', sa.Column('last_login', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the added column
    op.drop_column('users', 'last_login')
