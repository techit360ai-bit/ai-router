"""Guard the AI Router's execution-only commercial boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_removed_commercial_modules_and_endpoints_do_not_return() -> None:
    for filename in ("billing_system.py", "credit_ledger.py", "deployment_architecture.py"):
        assert not (ROOT / filename).exists()

    runtime_sources = [
        ROOT / "ai_router_core.py",
        ROOT / "ai_command_layer_impl.py",
        ROOT / "main.py",
        ROOT / "integration_guide.py",
        ROOT / "agent_orchestration.py",
        ROOT / "workers" / "workers.py",
    ]
    forbidden = (
        "SubscriptionTier", "CreditCost", "SubscriptionAccessControl",
        "HybridBillingService", "/api/v1/credits/", "/api/v1/billing/",
        "/api/v1/webhooks/stripe", "import stripe", "from billing_system",
        "from credit_ledger",
    )
    for source in runtime_sources:
        text = source.read_text(encoding="utf-8")
        for term in forbidden:
            assert term not in text, f"{term!r} returned in {source.name}"


def test_provider_prices_are_not_customer_prices() -> None:
    registry = (ROOT / "config" / "model_registry.json").read_text(encoding="utf-8")
    assert "input_cost_per_million" in registry
    assert "output_cost_per_million" in registry
    for forbidden in ("customer_price", "subscription_price", "plan_price", "credit_price"):
        assert forbidden not in registry
