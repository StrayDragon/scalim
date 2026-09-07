from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._types import ExampleResult


def format_results(results: Sequence[ExampleResult]) -> list[str]:
    lines: list[str] = []
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        kind = str(r.kind or "")
        prefix = f"[{status}]"
        if kind:
            prefix = f"{prefix}[{kind}]"
        first_line = str(r.summary or "").splitlines()[0] if r.summary else ""
        lines.append(f"{prefix} {r.example_id} - {first_line}")
    return lines


def summarize_failures(results: Sequence[ExampleResult]) -> str:
    failed = [r for r in results if not r.passed]
    if not failed:
        return ""
    parts: list[str] = []
    for r in failed:
        parts.append(f"\n[FAIL] {r.example_id}\n{r.summary}")
    return "\n".join(parts).lstrip("\n")


def exit_code(results: Sequence[ExampleResult]) -> int:
    return 0 if all(r.passed for r in results) else 1
