"""Thread-safe production hardening metrics and alert evaluation."""

from __future__ import annotations

from collections import Counter, defaultdict
from threading import Lock
from typing import Any, Dict, Mapping


class HardeningMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.counters: Counter[str] = Counter()
        self.labels: Dict[str, Counter[str]] = defaultdict(Counter)
        self.sums: Counter[str] = Counter()

    def increment(self, name: str, label: str = "total", value: int = 1) -> None:
        with self._lock:
            self.counters[name] += value
            self.labels[name][label] += value

    def observe_provider(self, event: Mapping[str, Any]) -> None:
        provider = str(event.get("provider") or "unknown")
        self.increment("provider_attempts", provider)
        if event.get("status") == "failed":
            self.increment("provider_failures", provider)
        with self._lock:
            self.sums["provider_latency_ms"] += float(event.get("latency_ms") or 0)
            self.sums["provider_cost_usd"] += float(event.get("provider_cost_usd") or 0)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            counters = dict(self.counters)
            labels = {name: dict(values) for name, values in self.labels.items()}
            sums = dict(self.sums)
        attempts = counters.get("provider_attempts", 0)
        failures = counters.get("provider_failures", 0)
        failure_rate = failures / attempts if attempts else 0.0
        alerts = []
        if attempts >= 20 and failure_rate > 0.2:
            alerts.append({"code": "provider_failure_rate_high", "severity": "critical", "value": round(failure_rate, 4)})
        if counters.get("fabricated_data_regressions", 0):
            alerts.append({"code": "fabricated_data_regression", "severity": "critical", "value": counters["fabricated_data_regressions"]})
        return {"counters": counters, "labels": labels, "sums": sums, "provider_failure_rate": round(failure_rate, 6), "alerts": alerts}


METRICS = HardeningMetrics()
