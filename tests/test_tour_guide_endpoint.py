"""
Contract test for Havi/Tour Guide context forwarding.

Run:
    python3 tests/test_tour_guide_endpoint.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")


def test_daily_check_in_forwards_request_body() -> None:
    main = importlib.import_module("main")
    seen = {}

    class FakeTourGuideService:
        def __init__(self, brain):
            seen["brain"] = brain

        async def daily_check_in(self, user, body):
            seen["user"] = user
            seen["body"] = body
            return {"momentum_score": 88}

    original_service = main.TourGuideService
    main.TourGuideService = FakeTourGuideService
    try:
        user = SimpleNamespace(user_id="u_test")
        body = {"source": "havi", "role": "founder", "firstLanding": True}
        result = asyncio.run(main.daily_check_in(body, user))
    finally:
        main.TourGuideService = original_service

    assert result == {"momentum_score": 88}
    assert seen["body"] == body
    assert seen["user"].user_id == "u_test"


def test_havi_conversation_route_is_registered_and_uses_router_context() -> None:
    main = importlib.import_module("main")
    seen = {}

    class FakeTourGuideService:
        def __init__(self, brain):
            seen["brain"] = brain

        async def converse(self, user, body):
            seen["user"] = user
            seen["body"] = body
            return {"message": "Live response"}

    original_service = main.TourGuideService
    main.TourGuideService = FakeTourGuideService
    try:
        user = SimpleNamespace(user_id="u_test")
        body = {"source": "havi", "role": "founder", "message": "What should I do next?"}
        result = asyncio.run(main.tour_guide_conversation(body, user))
    finally:
        main.TourGuideService = original_service

    assert result == {"message": "Live response"}
    assert seen["body"] == body


def test_first_landing_returns_role_specific_existing_platform_routes() -> None:
    main = importlib.import_module("main")

    class FakeBrain:
        async def trigger_agent(self, _agent_type, _context):
            return SimpleNamespace(
                output={"momentum_score": 50, "decay_factor": 1, "daily_plan": [], "ai_insights": ""},
                recommendations=[],
            )

    user = SimpleNamespace(role=SimpleNamespace(value="collaborator"))
    result = asyncio.run(main.TourGuideService(FakeBrain()).daily_check_in(
        user, {"role": "collaborator", "firstLanding": True},
    ))
    paths = {item["path"] for item in result["introduction"]["capabilities"]}
    assert "/collaborator/tasks" in paths
    assert "/collaborator/academy" in paths


if __name__ == "__main__":
    test_daily_check_in_forwards_request_body()
    print("tour guide endpoint contract OK")
