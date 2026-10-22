"""FastTrack product-stage inference: evidence-derived, manual override kept."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from stage_inference import infer_product_stage


def _recent_repo() -> dict:
    return {"languages": "TypeScript", "pushed_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()}


def test_no_signals_is_an_idea() -> None:
    result = infer_product_stage({})
    assert result["inferred"] == "idea"
    assert result["stage"] == "idea"
    assert result["source"] == "auto"
    assert result["confidence"] == "low"


def test_document_only_is_a_prototype() -> None:
    result = infer_product_stage({"document_id": "doc-1"})
    assert result["inferred"] == "prototype"
    assert result["signals"]["has_document"] is True


def test_recent_codebase_is_an_mvp() -> None:
    result = infer_product_stage({"repo_url": "https://github.com/acme/app"}, _recent_repo())
    assert result["inferred"] == "mvp"
    assert result["signals"]["recent_push"] is True


def test_stale_codebase_still_reads_as_prototype_not_mvp() -> None:
    stale = {"languages": "Go", "pushed_at": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()}
    result = infer_product_stage({"repo_url": "https://github.com/acme/app"}, stale)
    assert result["inferred"] == "prototype"


def test_beta_users_push_stage_up_the_ladder() -> None:
    assert infer_product_stage({}, beta_users_count=25)["inferred"] == "beta"
    assert infer_product_stage({}, beta_users_count=250)["inferred"] == "launched"
    assert infer_product_stage({}, has_revenue=True)["inferred"] == "launched"
    assert infer_product_stage({}, has_revenue=True, beta_users_count=5000)["inferred"] == "growth"


def test_manual_choice_overrides_but_mismatch_is_visible() -> None:
    result = infer_product_stage(
        {"stage": "mvp", "repo_url": "https://github.com/acme/app"},
        _recent_repo(),
    )
    assert result["stage"] == "mvp"
    assert result["source"] == "manual"
    assert result["mismatch"] is False


def test_manual_choice_that_conflicts_with_evidence_is_flagged() -> None:
    # Founder says "launched" but there is no repo, doc, revenue or users.
    result = infer_product_stage({"stage": "launched"})
    assert result["stage"] == "launched"
    assert result["inferred"] == "idea"
    assert result["mismatch"] is True


def test_unknown_manual_stage_falls_back_to_inference() -> None:
    result = infer_product_stage({"stage": "unicorn-ish", "document_id": "d"}, None)
    assert result["source"] == "auto"
    assert result["stage"] == "prototype"


def test_already_launched_flag_forces_launched_even_without_traction() -> None:
    result = infer_product_stage({"already_launched": True, "stage": "seed"})
    assert result["stage"] == "launched"
    assert result["source"] == "manual"
    assert result["inferred"] == "idea"
    assert result["mismatch"] is True


def test_product_stage_field_is_preferred_over_funding_stage() -> None:
    result = infer_product_stage({"stage": "seed", "product_stage": "prototype", "document_id": "d"})
    assert result["stage"] == "prototype"
    assert result["source"] == "manual"
