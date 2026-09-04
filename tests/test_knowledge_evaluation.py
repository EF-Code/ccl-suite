"""Fixed evaluation coverage for the local extractive answer MVP."""

from knowledge_evaluation import EVALUATION_CASES, evaluation_counts, run_evaluation


def test_fixed_evaluation_has_twenty_unique_cases() -> None:
    assert len(EVALUATION_CASES) == 20
    assert len({case.case_id for case in EVALUATION_CASES}) == 20
    assert {case.category for case in EVALUATION_CASES} == {"supported", "refusal", "conflict"}


def test_fixed_evaluation_meets_the_evidence_and_refusal_contract() -> None:
    results = run_evaluation()
    counts = evaluation_counts(results)

    assert counts == {
        "total": 20,
        "passed": 20,
        "failed": 0,
        "supported": 12,
        "refusal": 5,
        "conflict": 3,
    }
    assert all(result.passed for result in results)
    assert all(result.answer.citations == () for result in results if result.case.category == "refusal")
    assert all(len(result.answer.citations) == 2 for result in results if result.case.category == "conflict")
