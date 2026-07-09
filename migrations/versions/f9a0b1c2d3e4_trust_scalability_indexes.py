"""trust_scalability_indexes

Revision ID: f9a0b1c2d3e4
Revises: e8a9c0d1f2b3
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "e8a9c0d1f2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_watchlist_investor_project",
        "investor_watchlist",
        ["investor_id", "project_id"],
    )
    op.create_index(
        "idx_investor_trust_notes_investor_updated",
        "investor_trust_notes",
        ["investor_id", "updated_at"],
    )
    op.create_index(
        "idx_trust_profile_project_status",
        "trust_profiles",
        ["project_id", "verification_status"],
    )
    op.create_index(
        "idx_trust_profile_status_score",
        "trust_profiles",
        ["verification_status", "trust_score"],
    )
    op.create_index(
        "idx_trust_history_project_created",
        "trust_verification_history",
        ["project_id", "created_at"],
    )
    op.create_index(
        "idx_trust_history_source_expiry",
        "trust_verification_history",
        ["source", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_trust_history_source_expiry", table_name="trust_verification_history")
    op.drop_index("idx_trust_history_project_created", table_name="trust_verification_history")
    op.drop_index("idx_trust_profile_status_score", table_name="trust_profiles")
    op.drop_index("idx_trust_profile_project_status", table_name="trust_profiles")
    op.drop_index("idx_investor_trust_notes_investor_updated", table_name="investor_trust_notes")
    op.drop_index("idx_watchlist_investor_project", table_name="investor_watchlist")
