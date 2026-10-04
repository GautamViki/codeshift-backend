from dataclasses import dataclass
from typing import Sequence


@dataclass
class EvalSummary:
    total: int
    passed: int
    failed: int
    pass_rate: float
    prompt_version: str
    failures: list[str]


def summarize(results: Sequence[object]) -> EvalSummary:
    """Summarize a sequence of eval results into a single pass/fail report."""
    total = len(results)
    passed = sum(1 for result in results if getattr(result, "passed", False))
    failed = total - passed

    return EvalSummary(
        total=total,
        passed=passed,
        failed=failed,
        pass_rate=(passed / total) if total else 0.0,
        prompt_version=getattr(results[0], "prompt_version", "unknown") if results else "unknown",
        failures=[
            getattr(result, "case_id", "unknown")
            for result in results
            if not getattr(result, "passed", False)
        ],
    )
