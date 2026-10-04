"""
MCP client — thin async wrapper for calling the Plugins-MCP backend that lives
on the BACKEND repo (branch feat/plugins-mcp, mounted at /api/mcp on the Node
Express service).

Architecture decision (C10, 2026-06-20): ai-router → BACKEND/api/mcp,
server-to-server, with the END USER'S JWT forwarded. We picked this over
"frontend orchestrates" because the agent layer (AgentOrchestrator + 34 agents
in agent_orchestration.py) needs to invoke tools as part of multi-step
reasoning without round-tripping every call back through the browser. We
picked it over "no integration" because plugin tools are the only way agents
reach external systems (GitHub, etc.) — leaving them disconnected wastes
half the platform.

Auth flow: the caller passes the user's Bearer token; we forward it as-is.
BACKEND's mountTechitApi gate verifies it with the same JWT_SECRET this
service uses, so role enforcement happens on the BACKEND side using the
authenticated identity. No service-to-service token, no shared SA — the user
is the only authority.

Use:
    client = MCPClient()
    tools = await client.list_tools(user_token=ctx.bearer)
    result = await client.invoke('github', 'list_repositories', {}, user_token=ctx.bearer)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Base URL of the Plugins-MCP mount on BACKEND. Override via env in
# docker-compose / k8s; defaults to local dev where backend runs on :3000.
MCP_BASE_URL = os.getenv("MCP_BASE_URL", "http://localhost:3000/api/mcp")
MCP_TIMEOUT = float(os.getenv("MCP_TIMEOUT", "10.0"))


class MCPError(Exception):
    """Raised when the MCP backend returns a non-2xx or a malformed payload."""


class MCPClient:
    """Async client for BACKEND /api/mcp. One instance per process is fine."""

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None) -> None:
        self.base_url = (base_url or MCP_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else MCP_TIMEOUT

    async def list_tools(self, *, user_token: str) -> List[Dict[str, Any]]:
        """GET /api/mcp/tools — catalogue of plugin tools the user can invoke."""
        return await self._request("GET", "/tools", user_token=user_token)

    async def audit(self, *, user_token: str) -> List[Dict[str, Any]]:
        """GET /api/mcp/audit — immutable audit log."""
        return await self._request("GET", "/audit", user_token=user_token)

    async def contributions(self, *, user_token: str) -> List[Dict[str, Any]]:
        """GET /api/mcp/contributions — execution-intelligence feed."""
        return await self._request("GET", "/contributions", user_token=user_token)

    async def approvals(self, *, user_token: str) -> List[Dict[str, Any]]:
        """GET /api/mcp/approvals — pending/approved/rejected approval requests."""
        return await self._request("GET", "/approvals", user_token=user_token)

    async def invoke(
        self,
        plugin: str,
        tool: str,
        params: Dict[str, Any],
        *,
        user_token: str,
    ) -> Dict[str, Any]:
        """POST /api/mcp/invoke — execute a plugin tool as the authenticated user."""
        return await self._request(
            "POST", "/invoke",
            json={"plugin": plugin, "tool": tool, "params": params},
            user_token=user_token,
        )

    async def approve(self, request_id: str, *, user_token: str) -> Dict[str, Any]:
        """POST /api/mcp/approvals/:id/approve — approve a pending invocation."""
        return await self._request(
            "POST", f"/approvals/{request_id}/approve",
            json={},
            user_token=user_token,
        )

    async def connections(self, *, user_token: str) -> List[Dict[str, Any]]:
        """GET /api/mcp/connections — workspace credential status.

        Credentials are workspace-scoped (ADR-1). The workspace is derived
        server-side from the forwarded token, so the client never sends one, and
        the response carries presence/metadata only — never a secret (ADR-2).
        """
        return await self._request("GET", "/connections", user_token=user_token)

    async def is_connected(self, plugin: str, *, user_token: str) -> bool:
        """True when the acting workspace has a credential for `plugin`."""
        try:
            for row in await self.connections(user_token=user_token):
                if row.get("plugin") == plugin:
                    return bool(row.get("connected"))
        except MCPError:
            return False
        return False

    async def connect(
        self,
        plugin: str,
        credential: str,
        *,
        user_token: str,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """POST /api/mcp/connections/:plugin — store a workspace credential.

        Operator action: BACKEND requires a human admin/owner in the acting
        workspace. Never call this from an agent.
        """
        return await self._request(
            "POST", f"/connections/{plugin}",
            json={"credential": credential, "ttlSeconds": ttl_seconds},
            user_token=user_token,
        )

    async def disconnect(self, plugin: str, *, user_token: str) -> Dict[str, Any]:
        """DELETE /api/mcp/connections/:plugin — remove a workspace credential."""
        return await self._request("DELETE", f"/connections/{plugin}", user_token=user_token)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        user_token: str,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if not user_token:
            raise MCPError("user_token is required (forward the caller's Bearer token)")
        headers = {"Authorization": f"Bearer {user_token}"}
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                response = await http.request(method, url, headers=headers, json=json)
        except httpx.HTTPError as exc:
            logger.error("mcp_request_failed", method=method, path=path, error=str(exc))
            raise MCPError(f"MCP request failed: {exc}") from exc
        if response.status_code == 401:
            raise MCPError("MCP rejected the forwarded token (401)")
        if response.status_code >= 500:
            raise MCPError(f"MCP backend error {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as exc:
            raise MCPError(f"MCP returned non-JSON: {response.text[:200]}") from exc


# Process-singleton — agents grab this when they need tool execution.
_default_client: Optional[MCPClient] = None


def get_mcp_client() -> MCPClient:
    global _default_client
    if _default_client is None:
        _default_client = MCPClient()
    return _default_client
