"""merge execution-only and incubation-autonomy migration heads

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f, a1b2c3d4e5f6
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union


revision: str = "2b3c4d5e6f7a"
down_revision: Union[str, tuple[str, str], None] = ("1a2b3c4d5e6f", "a1b2c3d4e5f6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

