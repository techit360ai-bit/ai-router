#!/usr/bin/env python3
"""Operator-safe ai-router scalability smoke contract.

By default this script validates the probe plan and exits without network
traffic. Set AI_ROUTER_SCALABILITY_PROBE_ENABLED=true and AI_ROUTER_BASE_URL to
run a small capped probe against an authorized environment.
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, Iterable, List
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_CONCURRENCY = 2
DEFAULT_REQUESTS_PER_TARGET = 3
MAX_CONCURRENCY = 10
MAX_REQUESTS_PER_TARGET = 25
DEFAULT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class Target:
    name: str
    env: str
    path: str
    statuses: frozenset[int]
    p95_ms: int


TARGETS = (
    Target("ai-router-health", "AI_ROUTER_BASE_URL", "/health", frozenset({200}), 800),
    Target("ai-router-readiness", "AI_ROUTER_BASE_URL", "/ready", frozenset({200}), 800),
    Target("dashboard-auth-boundary", "AI_ROUTER_BASE_URL", "/api/v1/dashboard/intelligence", frozenset({401}), 800),
    Target("investor-trust-auth-boundary", "AI_ROUTER_BASE_URL", "/api/v1/investor/trust/startups", frozenset({401}), 800),
)


def _read_int(env: Dict[str, str], name: str, default: int, cap: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError:
        return default
    return min(max(value, 1), cap)


def build_plan(env: Dict[str, str] | None = None) -> Dict[str, object]:
    env = env or dict(os.environ)
    concurrency = _read_int(env, "AI_ROUTER_SCALABILITY_CONCURRENCY", DEFAULT_CONCURRENCY, MAX_CONCURRENCY)
    requests_per_target = _read_int(
        env,
        "AI_ROUTER_SCALABILITY_REQUESTS_PER_TARGET",
        DEFAULT_REQUESTS_PER_TARGET,
        MAX_REQUESTS_PER_TARGET,
    )
    timeout_seconds = _read_int(env, "AI_ROUTER_SCALABILITY_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS, 60)
    targets = []
    for target in TARGETS:
        base = env.get(target.env)
        targets.append(
            {
                "name": target.name,
                "configured": bool(base),
                "url": urljoin(base.rstrip("/") + "/", target.path.lstrip("/")) if base else None,
                "statuses": sorted(target.statuses),
                "p95_ms": target.p95_ms,
            }
        )
    return {
        "enabled": env.get("AI_ROUTER_SCALABILITY_PROBE_ENABLED") == "true",
        "limits": {
            "concurrency": concurrency,
            "requests_per_target": requests_per_target,
            "timeout_seconds": timeout_seconds,
        },
        "targets": targets,
    }


def _probe_once(url: str, timeout_seconds: int) -> tuple[int, float]:
    started = time.perf_counter()
    request = Request(url)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - operator-provided URL.
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except URLError as exc:
        raise RuntimeError(str(exc)) from exc
    return status, (time.perf_counter() - started) * 1000


def _p95(values: Iterable[float]) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, int(len(values) * 0.95 + 0.9999) - 1)
    return values[index]


def _run_target(target: Dict[str, object], limits: Dict[str, int]) -> Dict[str, object]:
    completed = 0
    failures = 0
    durations: List[float] = []
    total = limits["requests_per_target"]
    workers = min(limits["concurrency"], total)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_probe_once, str(target["url"]), limits["timeout_seconds"])
            for _ in range(total)
        ]
        for future in as_completed(futures):
            completed += 1
            try:
                status, duration_ms = future.result()
                durations.append(duration_ms)
                if status not in set(target["statuses"]):
                    failures += 1
            except Exception:
                failures += 1

    p95_ms = _p95(durations)
    return {
        "name": target["name"],
        "completed": completed,
        "failures": failures,
        "p95_ms": round(p95_ms, 2),
        "passed": failures == 0 and p95_ms <= int(target["p95_ms"]),
    }


def run(env: Dict[str, str] | None = None) -> Dict[str, object]:
    plan = build_plan(env)
    configured = [target for target in plan["targets"] if target["configured"]]
    if not plan["enabled"]:
        print(
            "ai-router scalability dry-run OK: "
            f"{len(plan['targets'])} targets, concurrency cap {plan['limits']['concurrency']}, "
            f"request cap {plan['limits']['requests_per_target']}"
        )
        return {"mode": "dry-run", "plan": plan}
    if not configured:
        raise RuntimeError("AI_ROUTER_SCALABILITY_PROBE_ENABLED=true requires AI_ROUTER_BASE_URL")

    results = [_run_target(target, plan["limits"]) for target in configured]
    for result in results:
        print(
            f"{'ok' if result['passed'] else 'fail'} {result['name']} "
            f"p95={result['p95_ms']}ms failures={result['failures']}"
        )
    failed = [result["name"] for result in results if not result["passed"]]
    if failed:
        raise RuntimeError(f"ai-router scalability probes failed: {', '.join(failed)}")
    return {"mode": "probe", "plan": plan, "results": results}


def main() -> int:
    try:
        run()
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
