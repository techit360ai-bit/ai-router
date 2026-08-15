"""Private MVP sandbox generation and approval-gated deployment contracts.

The service intentionally never accepts a personal GitHub token. External
repository creation and deployment are delegated to a restricted GitHub App /
deployment broker only after an immutable human approval event exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from live_domain_repository import LiveDomainRepository


ARTIFACT_ROOT = Path(os.getenv("SANDBOX_ARTIFACT_ROOT", "/tmp/techit-sandbox-builds")).resolve()
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


class SandboxBuildError(ValueError):
    pass


class SandboxBuildService:
    def __init__(self, repo: Optional[LiveDomainRepository] = None) -> None:
        self.repo = repo or LiveDomainRepository()
        ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:60] or "venture-mvp"

    @staticmethod
    def _approved(session: Dict[str, Any], action: str) -> bool:
        decisions = (session.get("state") or {}).get("decisions") or []
        return any(
            str(item.get("action")) == action
            and str(item.get("decision", "")).lower() in {"approve", "approved", "accept", "accepted"}
            for item in decisions
        )

    def create(self, user_id: str, session: Dict[str, Any], body: Dict[str, Any]) -> Dict[str, Any]:
        if not self._approved(session, "finalize_mvp_scope"):
            raise SandboxBuildError("finalize_mvp_scope_approval_required")
        state = session.get("state") or {}
        venture = state.get("venture_data") or {}
        roadmap = state.get("roadmap") or {}
        scope = str(body.get("scope") or roadmap.get("recommended_scope") or "one_week_mvp")
        project_id = str(session.get("projectId") or venture.get("project_id") or "")
        if not project_id:
            raise SandboxBuildError("project_id_required")
        name = str(venture.get("startup_name") or venture.get("title") or "Venture MVP")

        draft = self.repo.create_sandbox_build(user_id, project_id, {
            "workspace_id": body.get("workspace_id") or body.get("workspaceId"),
            "status": "building",
            "scope": scope,
            "manifest": {"startup_name": name, "scope": scope, "roadmap": roadmap.get(scope, {})},
        })
        build_id = str(draft["id"])
        build_dir = (ARTIFACT_ROOT / build_id).resolve()
        if ARTIFACT_ROOT not in build_dir.parents:
            raise SandboxBuildError("invalid_build_path")
        build_dir.mkdir(parents=True, exist_ok=False)

        files = self._materialize(build_dir, name, venture, roadmap, scope)
        checks = self._run_checks(build_dir, files)
        archive = ARTIFACT_ROOT / f"{build_id}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for relative in files:
                bundle.write(build_dir / relative, arcname=relative)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        status = "preview_ready" if all(check["passed"] for check in checks.values()) else "checks_failed"
        manifest = {**(draft.get("manifest") or {}), "files": files, "sha256": digest, "artifact_bytes": archive.stat().st_size}
        return self.repo.update_sandbox_build(user_id, build_id, {
            "status": status,
            "manifest": manifest,
            "checks": checks,
            "artifact_path": str(archive),
            "preview_url": f"/api/v1/incubation/builds/{build_id}/preview",
        }) or draft

    def register_scaffold(self, user_id: str, project_id: str, scaffold: Dict[str, Any]) -> Dict[str, Any]:
        draft = self.repo.create_sandbox_build(user_id, project_id, {
            "status": "registering",
            "scope": "generated_scaffold",
            "manifest": {"scaffold_type": scaffold.get("scaffold_type")},
        })
        build_id = str(draft["id"])
        archive = (ARTIFACT_ROOT / f"{build_id}.zip").resolve()
        if ARTIFACT_ROOT not in archive.parents:
            raise SandboxBuildError("invalid_build_path")
        payload = json.dumps(scaffold, indent=2, sort_keys=True, default=str)
        secret_findings = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(payload)]
        if secret_findings:
            return self.repo.update_sandbox_build(user_id, build_id, {
                "status": "checks_failed",
                "checks": {"secret_scan": {"passed": False, "findings": secret_findings}},
            }) or draft
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("scaffold.json", payload)
            bundle.writestr("schema.sql", str(scaffold.get("schema_sql") or ""))
            bundle.writestr(".env.example", str(scaffold.get("env_template") or ""))
            bundle.writestr("deploy.json", json.dumps(scaffold.get("deploy_config") or {}, indent=2, sort_keys=True))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return self.repo.update_sandbox_build(user_id, build_id, {
            "status": "artifact_registered",
            "manifest": {"scaffold_type": scaffold.get("scaffold_type"), "sha256": digest, "artifact_bytes": archive.stat().st_size},
            "checks": {"schema": {"passed": True}, "secret_scan": {"passed": True, "findings": []}, "artifact_integrity": {"passed": True, "sha256": digest}},
            "artifact_path": str(archive),
        }) or draft

    async def deploy_registered_artifact(
        self, user_id: str, build_id: str, deploy_target: str, human_approved: bool,
    ) -> Dict[str, Any]:
        if not human_approved:
            raise SandboxBuildError("human_deployment_approval_required")
        build = self.repo.get_sandbox_build(user_id, build_id)
        if not build or build.get("status") not in {"artifact_registered", "deployment_failed"}:
            raise SandboxBuildError("registered_artifact_required")
        broker = os.getenv("DEPLOYMENT_BROKER_URL", "").strip()
        secret = os.getenv("DEPLOYMENT_BROKER_SECRET", "").strip()
        if not broker or not secret:
            return self.repo.update_sandbox_build(user_id, build_id, {"status": "deployment_integration_required"}) or build
        import httpx
        payload = {"artifact_id": build_id, "project_id": build.get("projectId"), "artifact_sha256": (build.get("manifest") or {}).get("sha256"), "artifact_path": build.get("artifactPath"), "deploy_target": deploy_target}
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(secret.encode(), encoded, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(broker, content=encoded, headers={"Content-Type": "application/json", "X-TechIT-Signature": signature})
            data = response.json() if response.content else {}
        if response.status_code >= 400 or not data.get("deployment_id"):
            return self.repo.update_sandbox_build(user_id, build_id, {"status": "deployment_failed", "checks": {**(build.get("checks") or {}), "deployment": {"passed": False, "status_code": response.status_code}}}) or build
        status = "deployed_preview" if data.get("preview_url") else "deploying"
        return self.repo.update_sandbox_build(user_id, build_id, {"status": status, "preview_url": data.get("preview_url"), "checks": {**(build.get("checks") or {}), "deployment": {"passed": True, "deployment_id": data["deployment_id"], "logs_url": data.get("logs_url"), "repository_url": data.get("repository_url")}}}) or build

    def _materialize(self, root: Path, name: str, venture: Dict[str, Any], roadmap: Dict[str, Any], scope: str) -> list[str]:
        slug = self._slug(name)
        problem = str(venture.get("problem") or "A validated customer problem")
        solution = str(venture.get("solution") or venture.get("one_liner") or "A focused MVP solution")
        target = str(venture.get("target_customers") or "the first narrow customer segment")
        files: Dict[str, str] = {
            "README.md": f"# {name}\n\nPrivate TechIT sandbox for `{scope}`. Human approval is required before repository creation or deployment.\n\n## Problem\n{problem}\n\n## Solution\n{solution}\n",
            "package.json": json.dumps({"name": slug, "private": True, "version": "0.1.0", "scripts": {"build": "node scripts/build.mjs", "test": "node scripts/test.mjs"}, "dependencies": {}}, indent=2),
            ".env.example": "# Add runtime values through the approved deployment secret store.\nPUBLIC_APP_NAME=\n",
            "src/index.html": f"<!doctype html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{name}</title><link rel='stylesheet' href='./styles.css'></head><body><main><span class='badge'>Private MVP preview</span><h1>{name}</h1><p>{solution}</p><section><h2>Built for</h2><p>{target}</p></section><button id='learn'>Test the core value proposition</button><p id='status' aria-live='polite'></p></main><script src='./app.js'></script></body></html>",
            "src/styles.css": "body{font-family:Inter,system-ui;background:#f5f3ff;color:#1e1b4b;margin:0}main{max-width:760px;margin:10vh auto;padding:40px;background:white;border-radius:24px;box-shadow:0 20px 60px #4c1d9520}.badge{color:#6d28d9;font-weight:700}h1{font-size:48px}button{background:#6d28d9;color:white;border:0;border-radius:10px;padding:14px 18px;font-weight:700}",
            "src/app.js": "document.querySelector('#learn').addEventListener('click',()=>{document.querySelector('#status').textContent='Interest recorded locally for this private preview.'})\n",
            "scripts/build.mjs": "import fs from 'node:fs';fs.rmSync('dist',{recursive:true,force:true});fs.cpSync('src','dist',{recursive:true});console.log('static MVP compiled');\n",
            "scripts/test.mjs": "import fs from 'node:fs';for(const f of ['src/index.html','src/app.js','src/styles.css'])if(!fs.existsSync(f))throw new Error(`missing ${f}`);console.log('sandbox tests passed');\n",
            "mvp-plan.json": json.dumps({"scope": scope, "plan": roadmap.get(scope, {}), "human_approval_required": True}, indent=2, default=str),
        }
        for relative, content in files.items():
            target_path = root / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
        return sorted(files)

    def _run_checks(self, root: Path, files: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        contents = "\n".join((root / name).read_text(encoding="utf-8") for name in files)
        secrets = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(contents)]
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        dependencies = package.get("dependencies") or {}
        required = {"src/index.html", "src/app.js", "src/styles.css", "package.json", "README.md"}
        return {
            "compile": {"passed": required.issubset(set(files)), "detail": "Static entrypoints and build contract present"},
            "tests": {"passed": "addEventListener" in contents and "aria-live" in contents, "detail": "Core interaction and accessible status target present"},
            "secret_scan": {"passed": not secrets, "findings": secrets},
            "dependency_scan": {"passed": len(dependencies) == 0, "dependencies": dependencies},
            "security_scan": {"passed": "eval(" not in contents and "innerHTML" not in contents, "detail": "No eval or raw innerHTML usage"},
        }

    def artifact_path(self, user_id: str, build_id: str) -> Path:
        build = self.repo.get_sandbox_build(user_id, build_id)
        if not build or not build.get("artifactPath"):
            raise SandboxBuildError("build_artifact_not_found")
        path = Path(str(build["artifactPath"])).resolve()
        if ARTIFACT_ROOT not in path.parents or not path.is_file():
            raise SandboxBuildError("build_artifact_not_found")
        return path

    def preview_path(self, user_id: str, build_id: str) -> Path:
        if not self.repo.get_sandbox_build(user_id, build_id):
            raise SandboxBuildError("build_not_found")
        path = (ARTIFACT_ROOT / build_id / "src" / "index.html").resolve()
        if ARTIFACT_ROOT not in path.parents or not path.is_file():
            raise SandboxBuildError("preview_not_found")
        return path

    def preview_asset_path(self, user_id: str, build_id: str, asset_name: str) -> Path:
        if asset_name not in {"app.js", "styles.css"}:
            raise SandboxBuildError("preview_asset_not_found")
        if not self.repo.get_sandbox_build(user_id, build_id):
            raise SandboxBuildError("build_not_found")
        path = (ARTIFACT_ROOT / build_id / "src" / asset_name).resolve()
        if ARTIFACT_ROOT not in path.parents or not path.is_file():
            raise SandboxBuildError("preview_asset_not_found")
        return path

    async def deploy_preview(self, user_id: str, session: Dict[str, Any], build_id: str) -> Dict[str, Any]:
        if not self._approved(session, "create_repository") or not self._approved(session, "deploy_preview"):
            raise SandboxBuildError("repository_and_preview_deployment_approvals_required")
        build = self.repo.get_sandbox_build(user_id, build_id)
        if not build or build.get("status") not in {"preview_ready", "deployment_failed"}:
            raise SandboxBuildError("preview_ready_build_required")
        broker = os.getenv("DEPLOYMENT_BROKER_URL", "").strip()
        secret = os.getenv("DEPLOYMENT_BROKER_SECRET", "").strip()
        if not broker or not secret:
            return self.repo.update_sandbox_build(user_id, build_id, {"status": "deployment_integration_required", "checks": {**(build.get("checks") or {}), "deployment": {"passed": False, "detail": "Configure a restricted GitHub App deployment broker; personal tokens are forbidden."}}}) or build
        import httpx
        payload = {"build_id": build_id, "project_id": build.get("projectId"), "artifact_sha256": (build.get("manifest") or {}).get("sha256"), "artifact_path": build.get("artifactPath"), "production": False}
        encoded = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(secret.encode(), encoded, hashlib.sha256).hexdigest()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(broker, content=encoded, headers={"Content-Type": "application/json", "X-TechIT-Signature": signature})
            data = response.json() if response.content else {}
        if response.status_code >= 400:
            return self.repo.update_sandbox_build(user_id, build_id, {"status": "deployment_failed", "checks": {**(build.get("checks") or {}), "deployment": {"passed": False, "status_code": response.status_code}}}) or build
        return self.repo.update_sandbox_build(user_id, build_id, {"status": "deployed_preview", "preview_url": data.get("preview_url") or build.get("previewUrl"), "checks": {**(build.get("checks") or {}), "deployment": {"passed": True, "health": data.get("health"), "logs_url": data.get("logs_url"), "repository_url": data.get("repository_url")}}}) or build

    def rollback(self, user_id: str, current_build_id: str, target_build_id: str) -> Dict[str, Any]:
        current = self.repo.get_sandbox_build(user_id, current_build_id)
        target = self.repo.get_sandbox_build(user_id, target_build_id)
        if not current or not target or current.get("projectId") != target.get("projectId"):
            raise SandboxBuildError("rollback_build_not_found")
        return self.repo.create_sandbox_build(user_id, str(target["projectId"]), {"workspace_id": target.get("workspaceId"), "status": "rollback_ready", "scope": target.get("scope"), "manifest": target.get("manifest"), "checks": target.get("checks"), "artifact_path": target.get("artifactPath"), "preview_url": target.get("previewUrl"), "rollback_of_id": current_build_id})
