"""record scoring policy for persisted match decisions

Revision ID: ab12cd34ef56
Revises: c3d4e5f6a7b8
Create Date: 2026-08-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "ab12cd34ef56"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("policy_id", sa.String(length=120), nullable=True))
    op.create_index("idx_matches_policy_id", "matches", ["policy_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_matches_policy_id", table_name="matches")
    op.drop_column("matches", "policy_id")
