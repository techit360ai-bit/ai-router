"""Deterministic customer-evidence contract tests (no database required)."""

from customer_validation_service import MODES, OBJECTIVES, CustomerValidationError, CustomerValidationService, _hash, stage_questions


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
