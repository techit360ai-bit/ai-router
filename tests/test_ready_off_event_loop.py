"""/ready must not block the event loop.

Live provider key probes are blocking HTTP calls and the database checks are
synchronous SQLAlchemy calls. Run on the event loop, one slow provider or
database stalled every in-flight request for the duration of the probe.
"""

from __future__ import annotations

import asyncio
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "unit-test-secret-value-that-is-long-enough")
os.environ.setdefault("ENVIRONMENT", "development")

import main as main_module  # noqa: E402
import provider_key_health  # noqa: E402


def test_ready_runs_provider_probes_and_database_checks_off_the_event_loop(monkeypatch) -> None:
    seen: dict = {}

    def probe(*_args, **_kwargs):
        seen["probe"] = threading.get_ident()
        return {}

    class _Result:
        @staticmethod
        def scalar_one_or_none():
            return None

    class _Session:
        def execute(self, *_args, **_kwargs):
            seen["database"] = threading.get_ident()
            return _Result()

        def close(self) -> None:
            pass

    monkeypatch.setattr(provider_key_health, "provider_key_health", probe)
    monkeypatch.setattr(main_module, "_db_session_factory", lambda: _Session)

    async def run() -> int:
        loop_thread = threading.get_ident()
        await main_module.ready()
        return loop_thread

    loop_thread = asyncio.run(run())
    assert seen["probe"] != loop_thread
    assert seen["database"] != loop_thread
