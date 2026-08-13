from __future__ import annotations

import os

os.environ["ENVIRONMENT"] = "development"
os.environ.pop("DATABASE_URL", None)

from live_domain_repository import LiveDomainRepository, reset_memory_store_for_tests
from sandbox_build_service import SandboxBuildError, SandboxBuildService


def _session(repo: LiveDomainRepository):
    session = repo.create_incubation_session("u1", {"startup_name": "Sandbox Venture", "problem": "slow workflow", "solution": "focused workflow"}, "p1")
    repo.update_incubation_session("u1", session["id"], state_patch={"roadmap": {"recommended_scope": "one_day_prototype"}})
    return repo.get_incubation_session("u1", session["id"])


def test_sandbox_requires_human_scope_approval() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()
    session = _session(repo)
    service = SandboxBuildService(repo)
    try:
        service.create("u1", session, {"scope": "one_day_prototype"})
    except SandboxBuildError as exc:
        assert str(exc) == "finalize_mvp_scope_approval_required"
    else:
        raise AssertionError("sandbox generation must be approval gated")


def test_sandbox_materializes_scanned_private_artifact() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()
    session = _session(repo)
    repo.record_incubation_decision("u1", session["id"], "finalize_mvp_scope", "approved", "test")
    session = repo.get_incubation_session("u1", session["id"])
    build = SandboxBuildService(repo).create("u1", session, {"scope": "one_day_prototype"})
    assert build["status"] == "preview_ready"
    assert build["checks"]["secret_scan"]["passed"] is True
    assert os.path.isfile(build["artifactPath"])
