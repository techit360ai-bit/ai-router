"""Add proof-derived verified skill fields to trust projections."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ef12ab34cd56"
down_revision: Union[str, None] = "cd34ef56a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trust_profiles", sa.Column("verified_skills_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("trust_profiles", sa.Column("verified_skills", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("trust_profiles", "verified_skills")
    op.drop_column("trust_profiles", "verified_skills_count")
