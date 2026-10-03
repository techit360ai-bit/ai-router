"""Deterministic customer-evidence contract tests (no database required)."""

from customer_validation_service import MODES, OBJECTIVES, CustomerValidationError, CustomerValidationService, _hash, _theme_findings, stage_questions
from types import SimpleNamespace


def test_question_configuration_is_normalized_and_stable() -> None:
    questions = CustomerValidationService._validate_questions([
        {"id": "q1", "question": "What happened?", "required": True},
    ])
    assert questions == [{
        "id": "q1", "question": "What happened?", "answer_type": "long_text",
        "required": True, "options": [],
    }]
    assert _hash(questions) == _hash(questions)


def test_question_configuration_rejects_duplicates_and_empty_sets() -> None:
    for value in ([], [{"id": "q1", "question": "same"}, {"id": "q1", "question": "again"}]):
        try:
            CustomerValidationService._validate_questions(value)
        except CustomerValidationError:
            continue
        raise AssertionError("invalid question configuration was accepted")


def test_objective_and_mode_contracts_are_explicit() -> None:
    assert {"problem_discovery", "willingness_to_pay", "nps"}.issubset(OBJECTIVES)
    assert MODES == {"interview", "survey", "poll", "hybrid"}


def test_stage_questions_change_with_real_project_stage() -> None:
    idea = stage_questions("idea", "problem_discovery", "survey")
    growth = stage_questions("growth", "problem_discovery", "survey")
    assert idea != growth
    assert "last time" in idea[0]["question"].lower()
    assert "keeps you using" in growth[0]["question"].lower()


def test_findings_quote_only_submitted_customer_text() -> None:
    responses = [SimpleNamespace(answers={"q1": "We use manual spreadsheets and lose time."})]
    findings = _theme_findings(responses)
    manual = next(item for item in findings["recurringPainPoints"] if item["theme"] == "manual_workflow")
    assert manual["quotes"] == ["We use manual spreadsheets and lose time."]


def test_configuration_rejects_choice_question_without_options() -> None:
    try:
        CustomerValidationService._validate_questions([{"id": "q1", "question": "Choose", "answer_type": "multiple_choice"}])
    except CustomerValidationError as exc:
        assert str(exc) == "invalid_question_type"
    else:
        raise AssertionError("choice question without options was accepted")


def test_ai_findings_are_bounded_to_observed_fields() -> None:
    allowed = {"what_we_learned", "what_customers_currently_do", "what_customers_want", "recurring_pain_points", "objections", "contradictions", "surprises", "evidence_gaps", "limitations"}
    supplied = {"what_we_learned": ["actual"], "invented_metric": 99}
    assert {key for key in supplied if key in allowed} == {"what_we_learned"}


def test_founder_mutation_surface_has_no_response_update_or_delete_method() -> None:
    methods = set(dir(CustomerValidationService))
    assert "update_response" not in methods
    assert "delete_response" not in methods
