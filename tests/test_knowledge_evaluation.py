"""Fixed evaluation coverage for the local extractive answer MVP."""

from knowledge_evaluation import (
    EVALUATION_CASES,
    evaluation_counts,
    evaluation_passed,
    evaluation_thresholds,
    run_evaluation,
)


def test_fixed_evaluation_has_unique_cases() -> None:
    assert len(EVALUATION_CASES) == 24
    assert len({case.case_id for case in EVALUATION_CASES}) == 24
    assert {case.category for case in EVALUATION_CASES} == {
        "supported",
        "refusal",
        "conflict",
        "injection",
    }


def test_fixed_evaluation_meets_the_evidence_and_refusal_contract() -> None:
    results = run_evaluation()
    counts = evaluation_counts(results)

    assert counts == {
        "total": 24,
        "passed": 24,
        "failed": 0,
        "supported": 12,
        "refusal": 5,
        "conflict": 3,
        "injection": 4,
    }
    assert all(result.passed for result in results)
    assert all(result.answer.citations == () for result in results if result.case.category == "refusal")
    assert all(len(result.answer.citations) == 2 for result in results if result.case.category == "conflict")


def test_fixed_evaluation_requires_every_category_to_pass() -> None:
    results = run_evaluation()
    thresholds = evaluation_thresholds(results)

    assert evaluation_passed(results)
    assert set(thresholds) == {"overall", "supported", "refusal", "conflict", "injection"}
    assert all(gate["met"] is True for gate in thresholds.values())
    assert thresholds["injection"]["pass_rate"] == 1.0
