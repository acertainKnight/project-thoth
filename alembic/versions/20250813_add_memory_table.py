"""add memory table

Revision ID: 20250813_add_memory_table
Revises:
Create Date: 2025-08-13

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '20250813_add_memory_table'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create memory table for Letta integration."""
    # Create memory table for storing conversation memory
    op.create_table(
        'memory',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('agent_id', sa.String(), nullable=True),
        sa.Column('scope', sa.String(), nullable=False),  # core, episodic, archival
        sa.Column('role', sa.String(), nullable=False),  # user, assistant, system
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('salience_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indices for efficient querying
    op.create_index('idx_memory_user_id', 'memory', ['user_id'])
    op.create_index('idx_memory_user_scope', 'memory', ['user_id', 'scope'])
    op.create_index('idx_memory_created_at', 'memory', ['created_at'])
    op.create_index('idx_memory_salience', 'memory', ['salience_score'])


def downgrade() -> None:
    """Drop memory table."""
    op.drop_index('idx_memory_salience', table_name='memory')
    op.drop_index('idx_memory_created_at', table_name='memory')
    op.drop_index('idx_memory_user_scope', table_name='memory')
    op.drop_index('idx_memory_user_id', table_name='memory')
    op.drop_table('memory')
