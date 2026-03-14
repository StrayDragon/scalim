from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from ._types import EXAMPLE_KIND_ORACLE, ExampleResult


@dataclass(frozen=True)
class _ExampleCase:
    example_id: str
    kind: str
    run: Callable[[], ExampleResult]


def _safe_run(case: _ExampleCase) -> ExampleResult:
    try:
        result = case.run()
    except Exception as exc:  # noqa: BLE001
        return ExampleResult(
            example_id=case.example_id,
            passed=False,
            kind=case.kind,
            summary="{}: {}".format(type(exc).__name__, exc),
            details={"exc_type": type(exc).__name__, "message": str(exc)},
        )
    if result.example_id != case.example_id:
        return ExampleResult(
            example_id=case.example_id,
            passed=False,
            kind=case.kind,
            summary="mismatched example_id: {} != {}".format(result.example_id, case.example_id),
            details={"returned_example_id": result.example_id},
        )
    return result


def run_public_api_examples() -> List[ExampleResult]:
    from .public_api import iter_public_api_examples  # noqa: PLC0415

    cases = [_ExampleCase(example_id=eid, kind=kind, run=fn) for eid, kind, fn in iter_public_api_examples()]
    return [_safe_run(case) for case in cases]


def format_results(results: Sequence[ExampleResult]) -> List[str]:
    lines: List[str] = []
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        kind = str(r.kind or "")
        prefix = "[{}]".format(status)
        if kind:
            prefix = "{}[{}]".format(prefix, kind)
        first_line = str(r.summary or "").splitlines()[0] if r.summary else ""
        lines.append("{} {} - {}".format(prefix, r.example_id, first_line))
    return lines


def summarize_failures(results: Sequence[ExampleResult]) -> str:
    failed = [r for r in results if not r.passed]
    if not failed:
        return ""
    parts: List[str] = []
    for r in failed:
        parts.append("\n[FAIL] {}\n{}".format(r.example_id, r.summary))
    return "\n".join(parts).lstrip("\n")


def exit_code(results: Sequence[ExampleResult]) -> int:
    return 0 if all(r.passed for r in results) else 1


def coerce_demo_chapter_results(
    *,
    suite_id: str,
    results: Iterable[object],
    kind: str = EXAMPLE_KIND_ORACLE,
) -> List[ExampleResult]:
    out: List[ExampleResult] = []
    for item in results:
        chapter_id = getattr(item, "chapter_id", None)
        passed = bool(getattr(item, "passed", False))
        summary = str(getattr(item, "summary", "") or "")
        details = getattr(item, "details", None)
        example_id = "{}/{}".format(suite_id, chapter_id or type(item).__name__)
        payload: Optional[Dict[str, Any]] = None
        if isinstance(details, dict):
            payload = details
        out.append(ExampleResult(example_id=example_id, passed=passed, kind=kind, summary=summary, details=payload))
    return out
