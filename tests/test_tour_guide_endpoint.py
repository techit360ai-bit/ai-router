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


if __name__ == "__main__":
    test_daily_check_in_forwards_request_body()
    print("tour guide endpoint contract OK")
