"""investor_trust_notes

Revision ID: e8a9c0d1f2b3
Revises: d4f5e6a7b8c9
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e8a9c0d1f2b3"
down_revision: Union[str, None] = "d4f5e6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investor_trust_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("internal_rating", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("follow_up_reminder", sa.String(length=255), server_default="", nullable=False),
        sa.Column("checklist", postgresql.JSON(astext_type=sa.Text()), server_default="[]", nullable=False),
        sa.Column("bookmarked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investor_id", "project_id", name="uq_investor_trust_note"),
    )
    op.create_index(
        "idx_investor_trust_notes_investor",
        "investor_trust_notes",
        ["investor_id"],
    )
    op.create_index(
        "idx_investor_trust_notes_project",
        "investor_trust_notes",
        ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_investor_trust_notes_project", table_name="investor_trust_notes")
    op.drop_index("idx_investor_trust_notes_investor", table_name="investor_trust_notes")
    op.drop_table("investor_trust_notes")
