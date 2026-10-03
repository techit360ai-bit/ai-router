"""Service authentication for backend-requested admin telemetry.

User JWT roles never authorize this boundary. Only the platform backend may
request Router telemetry using the dedicated HMAC credential.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request


async def require_admin_telemetry_service(request: Request) -> str:
    secret = os.getenv("ADMIN_AI_ROUTER_TELEMETRY_SECRET", "")
    expected_service = os.getenv("ADMIN_AI_ROUTER_TELEMETRY_SERVICE_ID", "platform-backend")
    max_skew = int(os.getenv("ADMIN_AI_ROUTER_TELEMETRY_MAX_SKEW_SECONDS", "300"))
    if not secret:
        raise HTTPException(status_code=503, detail="admin telemetry service authentication is not configured")

    service_id = request.headers.get("x-techit-service-id", "")
    timestamp = request.headers.get("x-techit-timestamp", "")
    signature = request.headers.get("x-techit-signature", "")
    if service_id != expected_service or not timestamp or not signature:
        raise HTTPException(status_code=401, detail="admin telemetry service authentication required")
    try:
        numeric_timestamp = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="admin telemetry timestamp invalid") from exc
    if abs(int(time.time()) - numeric_timestamp) > max_skew:
        raise HTTPException(status_code=401, detail="admin telemetry timestamp invalid")

    body = (await request.body()).decode("utf-8")
    canonical = f"{timestamp}.{request.method.upper()}.{request.url.path}.{body}"
    expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="admin telemetry signature invalid")
    return service_id
