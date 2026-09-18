"""Shared test bootstrap for top-level AI Router modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_live_domain_test_memory():
    from live_domain_repository import disable_memory_store_for_tests

    disable_memory_store_for_tests()
    yield
    disable_memory_store_for_tests()
