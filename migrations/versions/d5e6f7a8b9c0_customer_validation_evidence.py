"""customer evidence validation core tables

Revision ID: d5e6f7a8b9c0
Revises: cd34ef56a7b9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, None] = "cd34ef56a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json():
    return postgresql.JSON(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "customer_validation_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("incubation_session_id", sa.UUID(), nullable=True),
        sa.Column("hypothesis_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("objective", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("questions", _json(), nullable=False),
        sa.Column("respondent_profile", _json(), nullable=False),
        sa.Column("source_configuration", _json(), nullable=False),
        sa.Column("target_respondents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("public_token_hash", sa.String(64), nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column("configuration_locked", sa.Boolean(), nullable=False),
        sa.Column("total_response_count", sa.Integer(), nullable=False),
        sa.Column("qualified_response_count", sa.Integer(), nullable=False),
        sa.Column("quality_counts", _json(), nullable=False),
        sa.Column("confidence_level", sa.String(30), nullable=False),
        sa.Column("synthesis_status", sa.String(30), nullable=False),
        sa.Column("latest_synthesis_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("activated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["incubation_session_id"], ["incubation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_token_hash"),
    )
    op.create_index("idx_customer_validation_owner", "customer_validation_sessions", ["owner_id", "updated_at"])
    op.create_index("idx_customer_validation_project", "customer_validation_sessions", ["project_id", "created_at"])
    op.create_index("idx_customer_validation_status_expiry", "customer_validation_sessions", ["status", "expires_at"])

    op.create_table(
        "customer_validation_responses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("answers", _json(), nullable=False),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("anonymous_browser_hash", sa.String(64), nullable=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("submission_kind", sa.String(40), nullable=False),
        sa.Column("quality_classification", sa.String(20), nullable=False),
        sa.Column("evidence_status", sa.String(20), nullable=False),
        sa.Column("quality_reasons", _json(), nullable=False),
        sa.Column("completion_percentage", sa.Float(), nullable=False),
        sa.Column("completion_seconds", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.TIMESTAMP(), nullable=False),
        sa.Column("classified_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("response_hash"),
    )
    op.create_index("idx_customer_validation_response_session", "customer_validation_responses", ["session_id", "received_at"])
    op.create_index("idx_customer_validation_response_quality", "customer_validation_responses", ["session_id", "quality_classification"])
    op.create_index("idx_customer_validation_response_answer_hash", "customer_validation_responses", ["session_id", "answer_hash"])

    op.create_table(
        "customer_validation_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("system_actor", sa.String(80), nullable=False),
        sa.Column("metadata_json", _json(), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_hash"),
    )
    op.create_index("idx_customer_validation_event_session", "customer_validation_events", ["session_id", "created_at"])
    op.create_index("idx_customer_validation_event_project", "customer_validation_events", ["project_id", "created_at"])

    op.create_table(
        "customer_validation_syntheses",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("findings", _json(), nullable=False),
        sa.Column("verdict", sa.String(40), nullable=False), sa.Column("confidence", sa.String(30), nullable=False),
        sa.Column("limitations", _json(), nullable=False), sa.Column("generated_by", sa.String(40), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("session_id", "version", name="uq_customer_validation_synthesis_version"),
    )
    op.create_index("idx_customer_validation_synthesis_session", "customer_validation_syntheses", ["session_id", "version"], unique=True)
    op.create_table(
        "customer_validation_recommendations",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("session_id", sa.UUID(), nullable=False), sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("deduplication_key", sa.String(160), nullable=False), sa.Column("title", sa.Text(), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", _json(), nullable=False), sa.Column("urgency", sa.String(20), nullable=False), sa.Column("expected_impact", sa.String(20)),
        sa.Column("estimated_effort", sa.String(20)), sa.Column("confidence", sa.String(30), nullable=False), sa.Column("source_engines", _json(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.TIMESTAMP(), nullable=False), sa.Column("updated_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_customer_validation_recommendation_project", "customer_validation_recommendations", ["project_id", "created_at"])
    op.create_table(
        "customer_validation_hypotheses",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("project_id", sa.UUID(), nullable=False), sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("evidence_summary", _json(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=False), sa.Column("updated_at", sa.TIMESTAMP(), nullable=False), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.ForeignKeyConstraint(["owner_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_customer_validation_hypothesis_project", "customer_validation_hypotheses", ["project_id", "updated_at"])
    op.create_foreign_key("fk_customer_validation_sessions_hypothesis", "customer_validation_sessions", "customer_validation_hypotheses", ["hypothesis_id"], ["id"])
    op.create_table(
        "customer_validation_bss_snapshots",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("session_id", sa.UUID(), nullable=False), sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(60), nullable=False), sa.Column("previous_score", sa.Float()), sa.Column("new_score", sa.Float()), sa.Column("delta", sa.Float()),
        sa.Column("confidence", sa.String(30), nullable=False), sa.Column("response_count", sa.Integer(), nullable=False), sa.Column("synthesis_hash", sa.String(64), nullable=False), sa.Column("calculation_version", sa.String(40), nullable=False), sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "customer_validation_shares",
        sa.Column("id", sa.UUID(), nullable=False), sa.Column("session_id", sa.UUID(), nullable=False), sa.Column("project_id", sa.UUID(), nullable=False), sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("scope", sa.String(30), nullable=False), sa.Column("share_token_hash", sa.String(64), nullable=False), sa.Column("report_hash", sa.String(64), nullable=False), sa.Column("report", _json(), nullable=False), sa.Column("expires_at", sa.TIMESTAMP()), sa.Column("created_at", sa.TIMESTAMP(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["customer_validation_sessions.id"]), sa.ForeignKeyConstraint(["project_id"], ["projects.id"]), sa.ForeignKeyConstraint(["owner_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("share_token_hash"),
    )


def downgrade() -> None:
    op.drop_constraint("fk_customer_validation_sessions_hypothesis", "customer_validation_sessions", type_="foreignkey")
    op.drop_table("customer_validation_shares")
    op.drop_table("customer_validation_bss_snapshots")
    op.drop_table("customer_validation_hypotheses")
    op.drop_table("customer_validation_recommendations")
    op.drop_table("customer_validation_syntheses")
    op.drop_table("customer_validation_events")
    op.drop_table("customer_validation_responses")
    op.drop_table("customer_validation_sessions")
