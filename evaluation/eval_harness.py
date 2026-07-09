import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ai_data_analysis_agent.agents.agent import run_agent
from ai_data_analysis_agent.core.llm import call_llm

REFUSAL_MESSAGE = (
    "I can only help with questions related to the connected data sources."
)
DATASETS_DIR = Path(__file__).parent / "datasets"


@dataclass
class EvalCase:
    id: str
    data_source: str
    question: str
    check_type: str  # "refusal" | "contains_number" | "contains_text" | "llm_judge"
    expected: Any = None
    category: str = "general"
    tolerance: float = 0.01  # relative tolerance for numeric checks


@dataclass
class EvalResult:
    case: EvalCase
    passed: bool
    actual: str
    latency: float
    detail: str = ""


def load_dataset(path: Path) -> list[EvalCase]:
    cases = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            cases.append(EvalCase(**json.loads(line)))
    return cases


def _extract_number(text: str) -> Optional[float]:
    match = re.search(r"-?\d[\d,]*\.?\d*", text.replace(",", ""))
    return float(match.group()) if match else None


def _check_refusal(actual: str, case: EvalCase) -> tuple[bool, str]:
    passed = REFUSAL_MESSAGE.strip().lower() in actual.strip().lower()
    return passed, "" if passed else "expected the scope-refusal message"


def _check_contains_number(actual: str, case: EvalCase) -> tuple[bool, str]:
    expected_num = float(case.expected)
    actual_num = _extract_number(actual)
    if actual_num is None:
        return False, "no number found in response"
    passed = abs(actual_num - expected_num) <= max(
        abs(expected_num) * case.tolerance, 1e-9
    )
    return passed, "" if passed else f"expected ~{expected_num}, got {actual_num}"


def _check_contains_text(actual: str, case: EvalCase) -> tuple[bool, str]:
    passed = str(case.expected).lower() in actual.lower()
    return passed, "" if passed else f"expected substring '{case.expected}' not found"


def _check_llm_judge(actual: str, case: EvalCase) -> tuple[bool, str]:
    prompt = f"""
You are grading an AI data analyst's answer.

Question: {case.question}
Expected answer (reference): {case.expected}
Actual answer given: {actual}

Does the actual answer correctly convey the same information as the
reference, allowing for differences in wording/formatting? Factual or
numeric differences mean NO. Reply with only YES or NO.
""".strip()
    verdict = (
        call_llm(
            prompt,
            langsmith_extra={
                "metadata": {"eval_case_id": case.id, "category": case.category},
                "tags": ["eval-judge"],
            },
        )
        .strip()
        .upper()
    )
    passed = verdict.startswith("YES")
    return passed, f"judge said: {verdict}"


_CHECKERS = {
    "refusal": _check_refusal,
    "contains_number": _check_contains_number,
    "contains_text": _check_contains_text,
    "llm_judge": _check_llm_judge,
}


def run_case(case: EvalCase, session_id: str = "eval-session") -> EvalResult:
    start = time.time()
    actual = run_agent(
        user_input=case.question, session_id=session_id, data_source=case.data_source
    )
    latency = time.time() - start

    checker = _CHECKERS[case.check_type]
    passed, detail = checker(actual, case)

    return EvalResult(
        case=case, passed=passed, actual=actual, latency=latency, detail=detail
    )


def run_suite(dataset_paths: list[Path]) -> list[EvalResult]:
    results = []
    for path in dataset_paths:
        for case in load_dataset(path):
            print(f"Running {case.id}...", end=" ", flush=True)
            result = run_case(case)
            print("PASS" if result.passed else f"FAIL ({result.detail})")
            results.append(result)
    return results


def summarize(results: list[EvalResult]) -> None:
    total = len(results)
    passed = sum(r.passed for r in results)

    print(f"\n{'=' * 60}")
    print(f"Overall: {passed}/{total} passed ({passed / total:.0%})")

    by_category: dict[str, list[EvalResult]] = {}
    for r in results:
        by_category.setdefault(r.case.category, []).append(r)

    print("\nBy category:")
    for category, cat_results in sorted(by_category.items()):
        cat_passed = sum(r.passed for r in cat_results)
        print(f"  {category}: {cat_passed}/{len(cat_results)}")

    avg_latency = sum(r.latency for r in results) / total if results else 0.0
    print(f"\nAverage latency: {avg_latency:.2f}s")

    failures = [r for r in results if not r.passed]
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  [{r.case.id}] {r.case.question!r}")
            print(f"    expected: {r.case.expected}")
            print(f"    actual:   {r.actual[:200]}")
            print(f"    reason:   {r.detail}")


def write_report(results: list[EvalResult], out_path: Path) -> None:
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total": len(results),
        "passed": sum(r.passed for r in results),
        "results": [
            {
                "id": r.case.id,
                "category": r.case.category,
                "question": r.case.question,
                "passed": r.passed,
                "actual": r.actual,
                "expected": r.case.expected,
                "detail": r.detail,
                "latency": round(r.latency, 3),
            }
            for r in results
        ],
    }
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    dataset_paths = [
        DATASETS_DIR / "sql_golden_set.jsonl",
        DATASETS_DIR / "excel_golden_set.jsonl",
    ]
    all_results = run_suite(dataset_paths)
    summarize(all_results)
    write_report(all_results, Path(__file__).parent / f"report_{int(time.time())}.json")
