from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

if TYPE_CHECKING:
    from ._types import ExampleResult


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
