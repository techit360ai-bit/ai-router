from __future__ import annotations

import os
import asyncio

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


def test_generated_scaffold_is_registered_as_immutable_artifact() -> None:
    reset_memory_store_for_tests()
    repo = LiveDomainRepository()
    service = SandboxBuildService(repo)
    artifact = service.register_scaffold("u1", "p1", {
        "scaffold_type": "nextjs_prisma",
        "schema_sql": "create table projects (id uuid primary key);",
        "env_template": "DATABASE_URL=",
        "deploy_config": {"deploy_steps": ["build"]},
    })

    assert artifact["status"] == "artifact_registered"
    assert artifact["manifest"]["sha256"]
    assert service.artifact_path("u1", artifact["id"]).is_file()


def test_registered_artifact_deployment_requires_connector(monkeypatch) -> None:
    reset_memory_store_for_tests()
    monkeypatch.delenv("DEPLOYMENT_BROKER_URL", raising=False)
    monkeypatch.delenv("DEPLOYMENT_BROKER_SECRET", raising=False)
    repo = LiveDomainRepository()
    service = SandboxBuildService(repo)
    artifact = service.register_scaffold("u1", "p1", {"scaffold_type": "nextjs_prisma"})

    result = asyncio.run(service.deploy_registered_artifact("u1", artifact["id"], "vercel", True))
    assert result["status"] == "deployment_integration_required"
    assert result.get("previewUrl") is None
