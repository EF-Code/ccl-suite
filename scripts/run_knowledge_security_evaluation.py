"""Run the sanitized prompt-injection corpus without printing its text."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Permit direct execution from the repository while keeping the scanner
# importable by tests and other tooling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge_security import scan_prompt_injection


CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "security"
    / "prompt-injection-cases.json"
)


def main() -> int:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    results: list[dict[str, object]] = []
    for case in cases:
        findings = scan_prompt_injection(str(case["text"]))
        observed = sorted({finding.category for finding in findings})
        expected = case["category"]
        passed = (
            not observed
            if expected is None
            else str(expected) in observed
        )
        results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "expected_category": expected,
                "observed_categories": observed,
                "passed": passed,
            }
        )

    attack_cases = [result for result in results if result["expected_category"]]
    benign_cases = [result for result in results if not result["expected_category"]]
    passed = sum(bool(result["passed"]) for result in results)
    attack_detected = sum(bool(result["passed"]) for result in attack_cases)
    benign_clean = sum(bool(result["passed"]) for result in benign_cases)
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "attack_cases": len(attack_cases),
        "attack_detection_rate": attack_detected / len(attack_cases)
        if attack_cases
        else 0.0,
        "benign_cases": len(benign_cases),
        "benign_clean_rate": benign_clean / len(benign_cases)
        if benign_cases
        else 0.0,
    }
    output = {
        "corpus_version": payload["version"],
        "summary": summary,
        "thresholds": {
            "required_attack_detection_rate": 1.0,
            "required_benign_clean_rate": 1.0,
        },
        "cases": results,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
