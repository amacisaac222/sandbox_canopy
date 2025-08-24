"""Add admin user columns

Revision ID: 1ec45058bcca
Revises: 5c99c1461274
Create Date: 2025-08-20 14:51:39.642907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ec45058bcca'
down_revision: Union[str, Sequence[str], None] = '5c99c1461274'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add missing columns to users table for admin functionality
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('auth_provider', sa.String(50), nullable=False, server_default='oidc'))
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the added columns
    op.drop_column('users', 'is_active')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'password_hash')
