from scripts.scalability_check import build_plan, run


def test_scalability_check_is_dry_run_by_default() -> None:
    result = run({})

    assert result["mode"] == "dry-run"
    assert result["plan"]["enabled"] is False
    assert len(result["plan"]["targets"]) >= 4


def test_scalability_check_caps_probe_pressure() -> None:
    plan = build_plan(
        {
            "AI_ROUTER_SCALABILITY_CONCURRENCY": "999",
            "AI_ROUTER_SCALABILITY_REQUESTS_PER_TARGET": "999",
            "AI_ROUTER_SCALABILITY_TIMEOUT_SECONDS": "999",
        }
    )

    assert plan["limits"]["concurrency"] == 10
    assert plan["limits"]["requests_per_target"] == 25
    assert plan["limits"]["timeout_seconds"] == 60


def test_scalability_check_builds_authorized_target_urls() -> None:
    plan = build_plan({"AI_ROUTER_BASE_URL": "https://ai-router.techit.example/"})
    target = next(item for item in plan["targets"] if item["name"] == "investor-trust-auth-boundary")

    assert target["configured"] is True
    assert target["url"] == "https://ai-router.techit.example/api/v1/investor/trust/startups"
