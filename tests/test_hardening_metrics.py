from hardening_metrics import HardeningMetrics


def test_metrics_raise_alerts_for_provider_failures_and_fabrication() -> None:
    metrics = HardeningMetrics()
    for _ in range(20):
        metrics.observe_provider({"provider": "test", "status": "failed", "latency_ms": 10, "provider_cost_usd": 0.01})
    metrics.increment("fabricated_data_regressions", "test")
    snapshot = metrics.snapshot()
    assert {alert["code"] for alert in snapshot["alerts"]} == {"provider_failure_rate_high", "fabricated_data_regression"}
