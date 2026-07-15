"""live_domain_tables

Revision ID: 0f1e2d3c4b5a
Revises: f9a0b1c2d3e4
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0f1e2d3c4b5a"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("origin", postgresql.JSON(astext_type=sa.Text()), nullable=True))

    op.create_table(
        "project_analyses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("venture_name", sa.String(length=255), nullable=True),
        sa.Column("blueprint", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("unicorn_potential_score", sa.Float(), nullable=True),
        sa.Column("investment_score", sa.Float(), nullable=True),
        sa.Column("pivot_needed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_analysis_owner", "project_analyses", ["owner_id"], unique=False)
    op.create_index("idx_analysis_project", "project_analyses", ["project_id", "created_at"], unique=False)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("seed_analysis_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["seed_analysis_id"], ["project_analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_workspace_owner", "workspaces", ["owner_id", "status"], unique=False)
    op.create_index("idx_workspace_project", "workspaces", ["project_id"], unique=False)

    op.create_table(
        "venture_intakes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("submission", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("structured_profile", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("promoted_project_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["promoted_project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_venture_intake_owner", "venture_intakes", ["owner_id", "created_at"], unique=False)
    op.create_index("idx_venture_intake_status", "venture_intakes", ["status"], unique=False)

    op.create_table(
        "venture_pipeline_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("module", sa.String(length=80), nullable=False),
        sa.Column("input_payload", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("blueprint", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_venture_pipeline_owner", "venture_pipeline_runs", ["owner_id", "created_at"], unique=False)
    op.create_index("idx_venture_pipeline_project", "venture_pipeline_runs", ["project_id", "created_at"], unique=False)

    op.create_table(
        "equity_grants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("equity_percent", sa.Float(), nullable=False),
        sa.Column("value_usd", sa.DECIMAL(precision=14, scale=2), nullable=True),
        sa.Column("vested_percent", sa.Float(), nullable=True),
        sa.Column("vesting_years", sa.Integer(), nullable=True),
        sa.Column("vesting_cliff_months", sa.Integer(), nullable=True),
        sa.Column("grant_date", sa.TIMESTAMP(), nullable=False),
        sa.Column("next_vest_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("next_vest_delta_percent", sa.Float(), nullable=True),
        sa.Column("dilution_protected", sa.Boolean(), nullable=True),
        sa.Column("role_at_grant", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_equity_project", "equity_grants", ["project_id"], unique=False)
    op.create_index("idx_equity_user", "equity_grants", ["user_id"], unique=False)
    op.create_index("idx_equity_user_project", "equity_grants", ["user_id", "project_id"], unique=False)

    op.create_table(
        "cap_table_entries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("percent", sa.Float(), nullable=False),
        sa.Column("holder_user_id", sa.UUID(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["holder_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_captable_project", "cap_table_entries", ["project_id", "sort_order"], unique=False)

    op.create_table(
        "dilution_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("new_shares_percent", sa.Float(), nullable=True),
        sa.Column("affected_user_id", sa.UUID(), nullable=True),
        sa.Column("consent_given", sa.Boolean(), nullable=True),
        sa.Column("protected_applied", sa.Boolean(), nullable=True),
        sa.Column("event_date", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["affected_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dilution_project", "dilution_events", ["project_id", "event_date"], unique=False)

    op.create_table(
        "collaborator_earnings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("earned_usd", sa.DECIMAL(precision=14, scale=2), nullable=True),
        sa.Column("pending_usd", sa.DECIMAL(precision=14, scale=2), nullable=True),
        sa.Column("revenue_share_percent", sa.Float(), nullable=True),
        sa.Column("contribution_note", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_earning_user", "collaborator_earnings", ["user_id"], unique=False)
    op.create_index("idx_earning_user_project", "collaborator_earnings", ["user_id", "project_id"], unique=False)

    op.create_table(
        "payouts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("month_iso", sa.String(length=7), nullable=False),
        sa.Column("amount_usd", sa.DECIMAL(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("destination", sa.String(length=120), nullable=True),
        sa.Column("initiated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("settled_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_payout_user", "payouts", ["user_id", "month_iso"], unique=False)

    op.create_table(
        "capital_pools",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("total_capital_usd", sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column("deployed_usd", sa.DECIMAL(precision=16, scale=2), nullable=True),
        sa.Column("funds_released_usd", sa.DECIMAL(precision=16, scale=2), nullable=True),
        sa.Column("startups_count", sa.Integer(), nullable=True),
        sa.Column("milestones_hit", sa.Integer(), nullable=True),
        sa.Column("roi_simulation", sa.Float(), nullable=True),
        sa.Column("min_readiness", sa.Integer(), nullable=True),
        sa.Column("max_per_startup_percent", sa.Float(), nullable=True),
        sa.Column("milestone_trigger", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_pool_investor", "capital_pools", ["investor_id", "status"], unique=False)

    op.create_table(
        "pool_milestone_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pool_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("milestone", sa.String(length=200), nullable=True),
        sa.Column("amount_usd", sa.DECIMAL(precision=16, scale=2), nullable=False),
        sa.Column("released", sa.Boolean(), nullable=True),
        sa.Column("triggered_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["pool_id"], ["capital_pools.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_release_pool", "pool_milestone_releases", ["pool_id", "released"], unique=False)

    op.create_table(
        "deal_rooms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("stage", sa.String(length=60), nullable=True),
        sa.Column("days_open", sa.Integer(), nullable=True),
        sa.Column("messages", sa.Integer(), nullable=True),
        sa.Column("docs", sa.Integer(), nullable=True),
        sa.Column("last_activity", sa.String(length=40), nullable=True),
        sa.Column("encrypted", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dealroom_investor", "deal_rooms", ["investor_id", "status"], unique=False)
    op.create_index("idx_dealroom_project", "deal_rooms", ["project_id"], unique=False)

    op.create_table(
        "term_sheets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_room_id", sa.UUID(), nullable=False),
        sa.Column("valuation_usd", sa.DECIMAL(precision=16, scale=2), nullable=True),
        sa.Column("investment_usd", sa.DECIMAL(precision=16, scale=2), nullable=True),
        sa.Column("equity_percent", sa.Float(), nullable=True),
        sa.Column("instrument", sa.String(length=40), nullable=True),
        sa.Column("discount_percent", sa.Float(), nullable=True),
        sa.Column("valuation_cap_usd", sa.DECIMAL(precision=16, scale=2), nullable=True),
        sa.Column("extra_terms", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["deal_room_id"], ["deal_rooms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_termsheet_room", "term_sheets", ["deal_room_id"], unique=False)

    op.create_table(
        "deal_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("deal_room_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("signed_by", sa.UUID(), nullable=True),
        sa.Column("signed_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["deal_room_id"], ["deal_rooms.id"]),
        sa.ForeignKeyConstraint(["signed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dealdoc_room", "deal_documents", ["deal_room_id", "status"], unique=False)

    op.create_table(
        "data_rooms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("doc_count", sa.Integer(), nullable=True),
        sa.Column("compliance_verified", sa.Boolean(), nullable=True),
        sa.Column("ai_governance_verified", sa.Boolean(), nullable=True),
        sa.Column("sections", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_label", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dataroom_project", "data_rooms", ["project_id"], unique=False)

    op.create_table(
        "data_room_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("data_room_id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("can_download", sa.Boolean(), nullable=True),
        sa.Column("granted", sa.Boolean(), nullable=True),
        sa.Column("granted_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("revoked_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["data_room_id"], ["data_rooms.id"]),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_dataroom_access", "data_room_access", ["data_room_id", "investor_id"], unique=False)

    op.create_table(
        "investor_reputation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("composite_score", sa.Integer(), nullable=True),
        sa.Column("month_change", sa.Integer(), nullable=True),
        sa.Column("response_speed", sa.Integer(), nullable=True),
        sa.Column("founder_rating", sa.Integer(), nullable=True),
        sa.Column("follow_through", sa.Integer(), nullable=True),
        sa.Column("value_add", sa.Integer(), nullable=True),
        sa.Column("portfolio_engagement", sa.Integer(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("total_investors", sa.Integer(), nullable=True),
        sa.Column("percentile", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inv_reputation", "investor_reputation", ["investor_id"], unique=False)

    op.create_table(
        "investor_reviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("investor_id", sa.UUID(), nullable=False),
        sa.Column("founder_name", sa.String(length=160), nullable=True),
        sa.Column("startup", sa.String(length=160), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("review_date", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["investor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inv_review", "investor_reviews", ["investor_id", "review_date"], unique=False)

    op.create_table(
        "hackathons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("theme", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("starts_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("ends_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hackathon_org", "hackathons", ["org_id", "status"], unique=False)

    op.create_table(
        "hackathon_teams",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hackathon_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("captain_id", sa.UUID(), nullable=True),
        sa.Column("members", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("is_solo", sa.Boolean(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column("registered_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["captain_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["hackathon_id"], ["hackathons.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hteam_captain", "hackathon_teams", ["captain_id"], unique=False)
    op.create_index("idx_hteam_hackathon", "hackathon_teams", ["hackathon_id", "status"], unique=False)

    op.create_table(
        "hackathon_briefs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("hackathon_id", sa.UUID(), nullable=False),
        sa.Column("problem", sa.Text(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("fields", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("problem_clarity_score", sa.Float(), nullable=True),
        sa.Column("team_momentum_score", sa.Float(), nullable=True),
        sa.Column("demo_readiness_hours", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("critiques", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["hackathon_id"], ["hackathons.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["hackathon_teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hbrief_team", "hackathon_briefs", ["team_id", "submitted_at"], unique=False)

    op.create_table(
        "hackathon_check_ins",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("hackathon_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("progress_delta", sa.Float(), nullable=True),
        sa.Column("activity_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["hackathon_id"], ["hackathons.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["hackathon_teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hcheckin_team", "hackathon_check_ins", ["team_id", "created_at"], unique=False)

    op.create_table(
        "hackathon_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("hackathon_id", sa.UUID(), nullable=False),
        sa.Column("judge_scores", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("platform_avg", sa.Float(), nullable=True),
        sa.Column("judge_avg_pct", sa.Float(), nullable=True),
        sa.Column("composite", sa.Float(), nullable=True),
        sa.Column("crs_band", sa.String(length=8), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["hackathon_id"], ["hackathons.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["hackathon_teams.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hscore_hackathon", "hackathon_scores", ["hackathon_id", "composite"], unique=False)

    op.create_table(
        "hackathon_team_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hackathon_id", sa.UUID(), nullable=False),
        sa.Column("team_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=True),
        sa.Column("idea", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("team", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("artifacts", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("stage", sa.String(length=80), nullable=True),
        sa.Column("reported_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(["hackathon_id"], ["hackathons.id"]),
        sa.ForeignKeyConstraint(["reported_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["hackathon_teams.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hreport_hackathon", "hackathon_team_reports", ["hackathon_id", "created_at"], unique=False)
    op.create_index("idx_hreport_team", "hackathon_team_reports", ["team_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_hreport_team", table_name="hackathon_team_reports")
    op.drop_index("idx_hreport_hackathon", table_name="hackathon_team_reports")
    op.drop_table("hackathon_team_reports")
    op.drop_index("idx_hscore_hackathon", table_name="hackathon_scores")
    op.drop_table("hackathon_scores")
    op.drop_index("idx_hcheckin_team", table_name="hackathon_check_ins")
    op.drop_table("hackathon_check_ins")
    op.drop_index("idx_hbrief_team", table_name="hackathon_briefs")
    op.drop_table("hackathon_briefs")
    op.drop_index("idx_hteam_hackathon", table_name="hackathon_teams")
    op.drop_index("idx_hteam_captain", table_name="hackathon_teams")
    op.drop_table("hackathon_teams")
    op.drop_index("idx_hackathon_org", table_name="hackathons")
    op.drop_table("hackathons")
    op.drop_index("idx_inv_review", table_name="investor_reviews")
    op.drop_table("investor_reviews")
    op.drop_index("idx_inv_reputation", table_name="investor_reputation")
    op.drop_table("investor_reputation")
    op.drop_index("idx_dataroom_access", table_name="data_room_access")
    op.drop_table("data_room_access")
    op.drop_index("idx_dataroom_project", table_name="data_rooms")
    op.drop_table("data_rooms")
    op.drop_index("idx_dealdoc_room", table_name="deal_documents")
    op.drop_table("deal_documents")
    op.drop_index("idx_termsheet_room", table_name="term_sheets")
    op.drop_table("term_sheets")
    op.drop_index("idx_dealroom_project", table_name="deal_rooms")
    op.drop_index("idx_dealroom_investor", table_name="deal_rooms")
    op.drop_table("deal_rooms")
    op.drop_index("idx_release_pool", table_name="pool_milestone_releases")
    op.drop_table("pool_milestone_releases")
    op.drop_index("idx_pool_investor", table_name="capital_pools")
    op.drop_table("capital_pools")
    op.drop_index("idx_payout_user", table_name="payouts")
    op.drop_table("payouts")
    op.drop_index("idx_earning_user_project", table_name="collaborator_earnings")
    op.drop_index("idx_earning_user", table_name="collaborator_earnings")
    op.drop_table("collaborator_earnings")
    op.drop_index("idx_dilution_project", table_name="dilution_events")
    op.drop_table("dilution_events")
    op.drop_index("idx_captable_project", table_name="cap_table_entries")
    op.drop_table("cap_table_entries")
    op.drop_index("idx_equity_user_project", table_name="equity_grants")
    op.drop_index("idx_equity_user", table_name="equity_grants")
    op.drop_index("idx_equity_project", table_name="equity_grants")
    op.drop_table("equity_grants")
    op.drop_index("idx_venture_pipeline_project", table_name="venture_pipeline_runs")
    op.drop_index("idx_venture_pipeline_owner", table_name="venture_pipeline_runs")
    op.drop_table("venture_pipeline_runs")
    op.drop_index("idx_venture_intake_status", table_name="venture_intakes")
    op.drop_index("idx_venture_intake_owner", table_name="venture_intakes")
    op.drop_table("venture_intakes")
    op.drop_index("idx_workspace_project", table_name="workspaces")
    op.drop_index("idx_workspace_owner", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("idx_analysis_project", table_name="project_analyses")
    op.drop_index("idx_analysis_owner", table_name="project_analyses")
    op.drop_table("project_analyses")
    op.drop_column("projects", "origin")
