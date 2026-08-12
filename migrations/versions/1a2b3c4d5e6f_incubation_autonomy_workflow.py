"""incubation autonomy workflow

Revision ID: 1a2b3c4d5e6f
Revises: 0f1e2d3c4b5a
Create Date: 2026-08-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "0f1e2d3c4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "incubation_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_phase", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_incubation_session_owner", "incubation_sessions", ["owner_id", "updated_at"])
    op.create_index("idx_incubation_session_project", "incubation_sessions", ["project_id", "updated_at"])

    op.create_table(
        "workspace_context_packs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("context_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_context_pack_owner", "workspace_context_packs", ["owner_id", "created_at"])
    op.create_index("idx_context_pack_workspace", "workspace_context_packs", ["workspace_id", "version"], unique=True)

    op.create_table(
        "sandbox_build_artifacts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("scope", sa.String(length=60), nullable=True),
        sa.Column("manifest", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("checks", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("approvals", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("preview_url", sa.Text(), nullable=True),
        sa.Column("rollback_of_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.ForeignKeyConstraint(["rollback_of_id"], ["sandbox_build_artifacts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sandbox_build_owner", "sandbox_build_artifacts", ["owner_id", "created_at"])
    op.create_index("idx_sandbox_build_project", "sandbox_build_artifacts", ["project_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_sandbox_build_project", table_name="sandbox_build_artifacts")
    op.drop_index("idx_sandbox_build_owner", table_name="sandbox_build_artifacts")
    op.drop_table("sandbox_build_artifacts")
    op.drop_index("idx_context_pack_workspace", table_name="workspace_context_packs")
    op.drop_index("idx_context_pack_owner", table_name="workspace_context_packs")
    op.drop_table("workspace_context_packs")
    op.drop_index("idx_incubation_session_project", table_name="incubation_sessions")
    op.drop_index("idx_incubation_session_owner", table_name="incubation_sessions")
    op.drop_table("incubation_sessions")

