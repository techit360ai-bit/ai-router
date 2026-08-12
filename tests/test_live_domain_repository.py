"""
Live domain repository contract tests.

These exercise the empty-state and persistence contracts used by founder,
workspace, collaborator, investor, organization, and feed sections without a
Postgres dependency. Production/staging still require DATABASE_URL.

Standalone (no pytest). Run:
    python3 tests/test_live_domain_repository.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["ENVIRONMENT"] = "development"
os.environ.pop("DATABASE_URL", None)

from live_domain_repository import (  # noqa: E402
    LiveDomainDatabaseUnavailable,
    LiveDomainRepository,
    reset_memory_store_for_tests,
)


def test_empty_states_are_empty_not_demo_records() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()

    assert repo.list_founder_projects("u1") == []
    assert repo.list_workspaces("u1") == []
    assert repo.collaborator_equity("u1")["holdings"] == []
    assert repo.collaborator_earnings("u1")["cashEarnings"] == []
    assert repo.investor_deal_flow("u1")["deal_flow"] == []
    assert repo.capital_pools("u1") == []
    assert repo.data_rooms("u1")["rooms"] == []
    assert repo.feed_posts("u1")["curated_feed"] == []
    assert repo.organization_dashboard("u1")["metrics"]["activePrograms"] == 0


def test_project_analysis_workspace_pipeline_is_persisted() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()

    created = repo.create_project("u1", {"title": "Live Venture", "stage": "mvp"})
    assert created["ok"] is True
    project_id = created["project"]["id"]

    repo.persist_analysis("u1", {"projectId": project_id, "startup_name": "Live Venture"}, {
        "venture_name": "Live Venture",
        "investment_score": 82,
        "unicorn_potential_score": 76,
        "blueprint": {"next": "build"},
    })
    workspace = repo.provision_workspace("u1", {"projectId": project_id, "name": "Live Workspace"})
    context = repo.workspace_context("u1", workspace["workspace"]["id"])
    exported = repo.latest_project_analysis("u1", project_id)

    assert repo.list_founder_projects("u1")[0]["title"] == "Live Venture"
    assert workspace["workspace"]["seededFromAnalysis"] is True
    assert context["blueprintAvailable"] is True
    assert context["venture"]["venture_name"] == "Live Venture"
    assert exported is not None
    assert exported["projectId"] == project_id
    assert exported["blueprint"]["investment_score"] == 82


def test_investor_and_collaborator_mutations_are_persisted() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()

    pool = repo.create_capital_pool("investor1", {"name": "Live Pool", "totalCapital": 1000})
    room = repo.deal_room_detail("investor1", "project1", {"mrr": 100})
    access = repo.grant_data_room_access("founder1", {"projectId": "project1", "investorId": "investor1"})
    withdrawal = repo.request_withdrawal("builder1", {"amount": 10})

    assert pool["pool"]["name"] == "Live Pool"
    assert room["meta"]["projectId"] == "project1"
    assert access["granted"] is True
    assert repo.data_rooms("investor1")["totals"]["activeRooms"] == 1
    assert withdrawal["ok"] is False
    assert withdrawal["available"] == 0


def test_production_requires_database_url() -> None:
    old_env = os.environ.get("ENVIRONMENT")
    old_database_url = os.environ.pop("DATABASE_URL", None)
    os.environ["ENVIRONMENT"] = "production"
    try:
        try:
            LiveDomainRepository()
        except LiveDomainDatabaseUnavailable:
            pass
        else:
            raise AssertionError("production repository must require DATABASE_URL")
    finally:
        if old_env is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = old_env
        if old_database_url is not None:
            os.environ["DATABASE_URL"] = old_database_url


def test_validation_sessions_context_packs_and_decisions_are_versioned() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()
    project = repo.create_project("u1", {"title": "Context Venture", "stage": "idea"})["project"]
    session = repo.create_incubation_session("u1", {"startup_name": "Context Venture"}, project["id"])
    assert session["status"] == "questions_pending"
    updated = repo.update_incubation_session("u1", session["id"], state_patch={"founder_answers": {"customer": "SMBs"}})
    assert updated["version"] == 2
    decision = repo.record_incubation_decision("u1", session["id"], "finalize_mvp_scope", "approved", "Smallest testable scope")
    assert decision["status"] == "approved"
    workspace = repo.provision_workspace("u1", {"projectId": project["id"]})["workspace"]
    pack = repo.persist_workspace_context_pack("u1", workspace["id"], project["id"], {"decisions": decision["state"]["decisions"]})
    assert pack["version"] == 1
    context = repo.workspace_context("u1", workspace["id"])
    assert context["contextVersion"] == 1
    assert context["contextPack"]["decisions"]


def test_sandbox_builds_are_private_and_versioned() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()
    first = repo.create_sandbox_build("u1", "p1", {"status": "preview_ready", "scope": "one_day_prototype", "checks": {"secret_scan": {"passed": True}}})
    second = repo.create_sandbox_build("u1", "p1", {"status": "rollback_ready", "scope": "one_day_prototype", "rollback_of_id": first["id"]})
    assert first["version"] == 1
    assert second["version"] == 2
    assert repo.get_sandbox_build("u1", first["id"])["status"] == "preview_ready"


def main() -> int:
    tests = [
        test_empty_states_are_empty_not_demo_records,
        test_project_analysis_workspace_pipeline_is_persisted,
        test_investor_and_collaborator_mutations_are_persisted,
        test_production_requires_database_url,
        test_validation_sessions_context_packs_and_decisions_are_versioned,
        test_sandbox_builds_are_private_and_versioned,
    ]
    for test in tests:
        try:
            test()
            print(f"  ok  {test.__name__}")
        except AssertionError as exc:
            print(f"  FAIL {test.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
