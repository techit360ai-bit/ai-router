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


def request(headers=None, path="/internal/admin/telemetry"):
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "method": "GET", "path": path, "raw_path": path.encode(), "query_string": b"", "headers": raw_headers, "scheme": "http", "server": ("test", 80), "client": ("test", 1)}
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    return Request(scope, receive=receive)


def signed_headers(service_id="platform-backend", secret=SECRET):
    timestamp = str(int(time.time()))
    canonical = f"{timestamp}.GET./internal/admin/telemetry."
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
