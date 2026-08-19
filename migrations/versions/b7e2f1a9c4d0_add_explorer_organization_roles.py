"""add explorer and organization role enum values

Revision ID: b7e2f1a9c4d0
Revises: 323a1fc13be9
"""

from alembic import op

revision = "b7e2f1a9c4d0"
down_revision = "cd34ef56a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'EXPLORER'")
    op.execute("ALTER TYPE roleenum ADD VALUE IF NOT EXISTS 'ORGANIZATION'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely in-place. Keep the
    # migration irreversible and preserve existing data.
    pass
