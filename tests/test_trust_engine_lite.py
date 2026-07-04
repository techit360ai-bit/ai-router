"""
Trust Engine Lite contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_engine_lite.py
Exit 0 = all asserts passed. Uses metadata-only local objects.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    AIRequest,
    CreditCost,
    ModelRouter,
    PromptEngine,
    SubscriptionAccessControl,
    SubscriptionTier,
    TaskType,
    UserContext,
    UserRole,
)
from billing_system import CREDIT_OPERATIONS  # noqa: E402
from trust_engine_lite import (  # noqa: E402
    FounderTrustProfile,
    TrustBadge,
    TrustEngineComputer,
    VerificationSource,
    VerificationStatus,
)


def _user_context() -> UserContext:
    return UserContext(
        user_id="u_trust",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=5,
        project_id="p_trust",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def test_trust_score_badges_and_sources_are_metadata_only() -> None:
    now = datetime.now()
    profile = FounderTrustProfile(
        founder_id="founder-1",
        email_verified=True,
        github_connected=True,
        domain_verified=True,
        deployment_live=True,
        github_repo_count=5,
        github_commit_count=100,
        github_contributor_count=2,
        deployments_30d=4,
        mau=250,
        team_verified_count=2,
        milestone_count=3,
    )

    result = TrustEngineComputer.compute(profile, now=now)

    assert result["trust_score"] == 74.75
    assert result["tier"] == "Verified"
    assert result["verification_status"] == VerificationStatus.VERIFIED.value
    assert set(result["signals"]) == {
        "email_verified",
        "github_connected",
        "domain_verified",
        "deployment_live",
        "product_activity",
        "team_verified",
        "milestones",
    }
    assert set(result["badges"]) == {
        "Verified Founder",
        "Verified Domain",
        "Active Development",
        "Team Verified",
        "Product Live",
        "Milestone Builder",
    }

    allowed_sources = {source.value for source in VerificationSource}
    for badge in result["badge_records"]:
        assert badge.source in allowed_sources
        assert badge.expires_at > badge.issued_at


def test_metadata_hash_is_stable_and_record_discards_payload() -> None:
    created_at = datetime(2026, 7, 1, 12, 0, 0)
    metadata_a = {"repo_count": 3, "last_activity": "2026-07-01", "languages": ["Python"]}
    metadata_b = {"languages": ["Python"], "last_activity": "2026-07-01", "repo_count": 3}

    hash_a = TrustEngineComputer.hash_metadata(metadata_a)
    hash_b = TrustEngineComputer.hash_metadata(metadata_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64
    assert "Python" not in hash_a

    record = TrustEngineComputer.build_verification_record(
        verification_id="ver-1",
        subject_id="founder-1",
        subject_type="founder",
        source=VerificationSource.GITHUB.value,
        status=VerificationStatus.VERIFIED,
        confidence=0.98,
        metadata=metadata_a,
        created_at=created_at,
        reference_id="github-connection-1",
    )

    assert record.metadata_hash == hash_a
    assert record.expires_at == created_at + timedelta(days=1)
    assert record.event_type == "github_verified"
    assert not hasattr(record, "metadata")
    assert not hasattr(record, "raw_payload")


def test_stale_detection_and_badge_expiry_are_explicit() -> None:
    now = datetime.now()

    assert TrustEngineComputer.is_verification_stale(
        VerificationSource.GITHUB.value,
        now - timedelta(hours=25),
        now=now,
    )
    assert not TrustEngineComputer.is_verification_stale(
        VerificationSource.GITHUB.value,
        now - timedelta(hours=23),
        now=now,
    )
    assert TrustEngineComputer.is_verification_stale(
        "unknown-source",
        now - timedelta(days=8),
        now=now,
    )

    expired_badge = TrustBadge(
        badge_type="verified_domain",
        label="Verified Domain",
        source=VerificationSource.DOMAIN.value,
        issued_at=now - timedelta(days=91),
        expires_at=now - timedelta(days=1),
    )
    assert not expired_badge.is_active


def test_trust_tasks_are_registered_for_free_tier_routing_and_prompts() -> None:
    router = ModelRouter()
    prompt_engine = PromptEngine()
    ctx = _user_context()

    for task in (
        TaskType.TRUST_VERIFY_FOUNDER,
        TaskType.TRUST_VERIFY_ORG,
        TaskType.TRUST_MILESTONE_REVIEW,
    ):
        request = AIRequest(task_type=task, user_context=ctx, input_data={})
        assert CreditCost.cost_for(task) == 1
        assert SubscriptionAccessControl.is_allowed(SubscriptionTier.FREE, task)
        assert router.select_chain(request)
        assert task in prompt_engine.SYSTEM_PROMPTS
        prompt = prompt_engine.SYSTEM_PROMPTS[task].lower()
        assert "metadata" in prompt
        assert "never" in prompt


def test_hybrid_billing_operations_are_registered() -> None:
    for operation_id in (
        "trust_verify_founder",
        "trust_verify_org",
        "trust_milestone_review",
    ):
        operation = CREDIT_OPERATIONS[operation_id]
        assert operation.credit_cost == 1
        assert operation.min_plan_id == "founder_free"


def test_schema_columns_do_not_store_raw_provider_payloads() -> None:
    schema = Path(__file__).resolve().parents[1] / "database_schema.py"
    text = schema.read_text(encoding="utf-8")
    forbidden = (
        "token",
        "secret",
        "raw",
        "payload",
        "source_code",
        "repository_content",
        "contact_list",
        "document_blob",
        "analytics_event",
    )

    for table_name in (
        "trust_profiles",
        "trust_verification_history",
        "trust_timeline_events",
        "trust_badge_snapshots",
    ):
        start = text.index(f'__tablename__ = "{table_name}"')
        next_class = text.find("\nclass ", start + 1)
        block = text[start: next_class if next_class != -1 else len(text)]
        column_lines = [line.lower() for line in block.splitlines() if "= column(" in line.lower()]

        assert column_lines, f"no columns found for {table_name}"
        for line in column_lines:
            assert not any(term in line for term in forbidden), line

    assert "INSERT-only by policy" in text
    assert "Append-only public/private trust timeline event" in text


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} Trust Engine Lite tests passed.")
