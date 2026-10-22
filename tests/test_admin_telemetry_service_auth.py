import asyncio
import hashlib
import hmac
import os
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from admin_service_auth import require_admin_telemetry_service
from main import _role_from_claim
from ai_router_core import UserRole


SECRET = "admin-telemetry-test-secret-at-least-32-characters"


def request(headers=None, path="/internal/admin/telemetry", *, method="GET", body=b"", raw_path=None, query_string=b""):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": (raw_path or path).encode(),
        "query_string": query_string,
        "headers": raw_headers,
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 1),
    }
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}
    return Request(scope, receive=receive)


def signed_headers(service_id="platform-backend", secret=SECRET, *, method="GET", path="/internal/admin/telemetry", body=""):
    timestamp = str(int(time.time()))
    canonical = f"{timestamp}.{method}.{path}.{body}"
    signature = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return {"x-techit-service-id": service_id, "x-techit-timestamp": timestamp, "x-techit-signature": signature}


def test_super_admin_is_not_an_ai_router_admin_role():
    assert _role_from_claim("super_admin") == UserRole.EXPLORER


@pytest.mark.parametrize("role", ["founder", "investor", "super_admin"])
def test_user_bearer_roles_cannot_authorize_admin_telemetry(monkeypatch, role):
    monkeypatch.setenv("ADMIN_AI_ROUTER_TELEMETRY_SECRET", SECRET)
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_admin_telemetry_service(request({"authorization": f"Bearer token-for-{role}"})))
    assert error.value.status_code == 401


def test_backend_service_signature_authorizes_admin_telemetry(monkeypatch):
    monkeypatch.setenv("ADMIN_AI_ROUTER_TELEMETRY_SECRET", SECRET)
    assert asyncio.run(require_admin_telemetry_service(request(signed_headers()))) == "platform-backend"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/internal/admin/provider-status", ""),
        ("POST", "/internal/admin/provider-refresh", '{"provider_ids":["openai"]}'),
        ("PATCH", "/internal/admin/provider-policy", '{"enabled":false}'),
        ("PATCH", "/internal/admin/model-leases/openai/gpt-4.1", '{"action":"disable"}'),
    ],
)
def test_admin_control_paths_accept_backend_service_signature(monkeypatch, method, path, body):
    monkeypatch.setenv("ADMIN_AI_ROUTER_TELEMETRY_SECRET", SECRET)
    headers = signed_headers(method=method, path=path, body=body)
    received = request(headers, path, method=method, body=body.encode())
    assert asyncio.run(require_admin_telemetry_service(received)) == "platform-backend"


def test_query_string_is_not_part_of_the_signed_path(monkeypatch):
    monkeypatch.setenv("ADMIN_AI_ROUTER_TELEMETRY_SECRET", SECRET)
    path = "/internal/admin/provider-status"
    received = request(
        signed_headers(path=path),
        path,
        raw_path=f"{path}?refresh_credentials=true",
        query_string=b"refresh_credentials=true",
    )
    assert asyncio.run(require_admin_telemetry_service(received)) == "platform-backend"
