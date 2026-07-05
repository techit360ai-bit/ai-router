"""
Trust integration adapter contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_integration_adapters.py
Exit 0 = all asserts passed. Uses local metadata only; no provider network calls.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Any, Callable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from integration_guide import TechITAIBrain, TrustVerificationService  # noqa: E402
from main import app  # noqa: E402
from trust_engine_lite import VerificationSource, VerificationStatus  # noqa: E402
from trust_integration_adapters import (  # noqa: E402
    TrustIntegrationAdapterRegistry,
    TrustRefreshPlanner,
    UnsupportedTrustProvider,
)


def _user() -> UserContext:
    return UserContext(
        user_id="u_trust_adapter",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=10,
        project_id="p_trust_adapter",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _service() -> TrustVerificationService:
    return TrustVerificationService(TechITAIBrain())


def test_registry_manifests_are_privacy_first_and_read_only() -> None:
    registry = TrustIntegrationAdapterRegistry.default()
    manifests = registry.manifests()
    providers = {manifest["provider"] for manifest in manifests}

    assert {"github", "vercel", "firebase", "supabase", "domain", "linkedin"}.issubset(providers)
    for manifest in manifests:
        assert manifest["raw_payload_stored"] is False
        assert "token" not in " ".join(manifest["stored_fields"]).lower()
        assert "payload" not in " ".join(manifest["stored_fields"]).lower()
        assert manifest["sync_frequency_seconds"] > 0
        assert manifest["revocation_supported"] is True
        assert "secret-manager" in manifest["token_policy"]


def test_github_adapter_normalizes_counts_and_drops_raw_provider_fields() -> None:
    result = TrustIntegrationAdapterRegistry.default().normalize(
        "github",
        {
            "repo_count": 4,
            "commit_count": 88,
            "contributor_count": 3,
            "last_activity": "2026-07-04T10:00:00",
            "oauth_token": "drop-me",
            "raw_payload": {"repositories": ["drop-me"]},
            "repository_contents": "drop-me",
        },
        now=datetime(2026, 7, 5, 0, 0, 0),
    )

    data = result.to_dict()
    assert data["provider"] == "github"
    assert data["source"] == VerificationSource.GITHUB.value
    assert data["status"] == VerificationStatus.VERIFIED.value
    assert data["metadata"]["github_repo_count"] == 4
    assert data["metadata"]["github_commit_count"] == 88
    assert data["metadata"]["github_contributor_count"] == 3
    assert data["metadata"]["verified"] is True
    assert "oauth_token" in data["dropped_fields"]
    assert "raw_payload" in data["dropped_fields"]
    assert "repository_contents" in data["dropped_fields"]
    assert data["raw_payload_stored"] is False
    assert data["tokens_stored"] is False
    assert "drop-me" not in data["metadata_hash"]


def test_deployment_and_product_adapters_keep_only_aggregate_metadata() -> None:
    registry = TrustIntegrationAdapterRegistry.default()
    deploy = registry.normalize(
        "vercel",
        {
            "deployment_status": "ready",
            "deployments_this_month": 9,
            "last_deployment": "2026-07-05T01:00:00",
            "environment_variables": "drop-me",
            "build_artifacts": "drop-me",
            "logs": "drop-me",
        },
    )
    product = registry.normalize(
        "supabase",
        {
            "mau": 120,
            "dau": 18,
            "growth_pct": 12.5,
            "retention_pct": 42.0,
            "user_email": "drop@example.com",
            "analytics_events": 500,
            "sessions": 25,
        },
    )

    assert deploy.source == VerificationSource.DEPLOYMENT.value
    assert deploy.metadata["platform"] == "vercel"
    assert deploy.metadata["deployment_live"] is True
    assert deploy.metadata["deployments_30d"] == 9
    assert "environment_variables" in deploy.dropped_fields
    assert "build_artifacts" in deploy.dropped_fields
    assert "logs" in deploy.dropped_fields

    assert product.source == VerificationSource.PRODUCT_ANALYTICS.value
    assert product.metadata["provider"] == "supabase"
    assert product.metadata["mau"] == 120
    assert product.metadata["dau"] == 18
    assert product.metadata["growth_rate_pct"] == 12.5
    assert product.metadata["retention_rate_pct"] == 42.0
    assert "user_email" in product.dropped_fields
    assert "analytics_events" in product.dropped_fields
    assert "sessions" in product.dropped_fields


def test_trust_service_adapter_handoff_uses_metadata_only_contract() -> None:
    result = _service().verify_adapter_payload(
        _user(),
        "github",
        {
            "repo_count": 2,
            "commit_count": 20,
            "contributor_count": 1,
            "source_code": "drop-me",
            "oauth_token": "drop-me",
        },
        db=None,
    )

    assert result["source"] == VerificationSource.GITHUB.value
    assert result["status"] == VerificationStatus.VERIFIED.value
    assert result["metadata_stored"]["github_repo_count"] == 2
    assert result["metadata_stored"]["github_commit_count"] == 20
    assert result["raw_payload_stored"] is False
    assert result["adapter"]["provider"] == "github"
    assert result["adapter"]["tokens_stored"] is False
    assert "source_code" in result["dropped_fields"]
    assert "oauth_token" in result["dropped_fields"]


def test_refresh_planner_marks_due_expired_failed_and_disconnected_without_mutation() -> None:
    now = datetime(2026, 7, 5, 12, 0, 0)
    plan = TrustRefreshPlanner().plan(
        [
            {
                "source": "github",
                "provider": "github",
                "status": "verified",
                "connected": True,
                "last_sync_at": (now - timedelta(hours=23)).isoformat(),
            },
            {
                "source": "deployment",
                "provider": "vercel",
                "status": "verified",
                "connected": True,
                "last_sync_at": (now - timedelta(hours=13)).isoformat(),
            },
            {
                "source": "domain",
                "provider": "domain",
                "status": "failed",
                "connected": True,
                "last_sync_at": (now - timedelta(days=1)).isoformat(),
            },
            {
                "source": "product_analytics",
                "provider": "firebase",
                "status": "disconnected",
                "connected": False,
                "last_sync_at": (now - timedelta(days=1)).isoformat(),
            },
        ],
        now=now,
    )

    by_provider = {item["provider"]: item for item in plan["items"]}
    assert by_provider["github"]["verification_state"] == VerificationStatus.VERIFIED.value
    assert by_provider["github"]["should_refresh"] is False
    assert by_provider["vercel"]["verification_state"] == VerificationStatus.EXPIRED.value
    assert by_provider["vercel"]["should_refresh"] is True
    assert by_provider["vercel"]["notification_type"] == "trust_verification_expired"
    assert by_provider["domain"]["verification_state"] == VerificationStatus.FAILED.value
    assert by_provider["domain"]["notification_type"] == "trust_verification_failed"
    assert by_provider["firebase"]["verification_state"] == VerificationStatus.DISCONNECTED.value
    assert by_provider["firebase"]["should_refresh"] is False
    assert plan["privacy"]["failure_deletes_existing_data"] is False


def test_service_manifests_refresh_plan_and_routes_are_registered() -> None:
    service = _service()
    manifests = service.get_integration_manifests()
    single = service.get_integration_manifests("github")
    refresh_plan = service.get_refresh_plan(
        _user(),
        {"connections": [{"source": "github", "provider": "github", "connected": True}]},
    )
    routes = {getattr(route, "path", "") for route in app.routes}

    assert len(manifests["integrations"]) >= 10
    assert single["integrations"][0]["provider"] == "github"
    assert refresh_plan["due_count"] == 1
    assert {
        "/api/v1/trust/integrations",
        "/api/v1/trust/adapters/{provider}/verify",
        "/api/v1/trust/refresh-plan",
    }.issubset(routes)


def test_unsupported_provider_is_rejected() -> None:
    try:
        TrustIntegrationAdapterRegistry.default().manifest("banking")
    except UnsupportedTrustProvider as exc:
        assert "Unsupported trust integration provider" in str(exc)
    else:
        raise AssertionError("unsupported provider did not raise")


def main() -> int:
    tests: List[Callable[[], None]] = [
        test_registry_manifests_are_privacy_first_and_read_only,
        test_github_adapter_normalizes_counts_and_drops_raw_provider_fields,
        test_deployment_and_product_adapters_keep_only_aggregate_metadata,
        test_trust_service_adapter_handoff_uses_metadata_only_contract,
        test_refresh_planner_marks_due_expired_failed_and_disconnected_without_mutation,
        test_service_manifests_refresh_plan_and_routes_are_registered,
        test_unsupported_provider_is_rejected,
    ]
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            print(f"FAIL {test.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {test.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\nAll {len(tests)} Trust integration adapter tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
