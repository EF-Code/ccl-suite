"""Run the fixed Knowledge Base Answer evaluation suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Permit direct execution from the repository while keeping the evaluation
# implementation importable by tests and other tooling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge_evaluation import evaluation_counts, run_evaluation


def main() -> int:
    results = run_evaluation()
    payload = {
        "summary": evaluation_counts(results),
        "cases": [
            {
                "id": result.case.case_id,
                "category": result.case.category,
                "status": result.answer.status,
                "refusal_reason": result.answer.refusal_reason,
                "citation_count": len(result.answer.citations),
                "passed": result.passed,
                "failure_reason": result.failure_reason,
            }
            for result in results
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
