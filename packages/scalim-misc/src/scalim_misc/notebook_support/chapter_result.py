# force-en
"""Cells-native ``chapter_result`` assembly helpers (marimo-free, headless importable).

The cells-native chapter contract:

- The chapter execution main path lives in marimo cells; the final cell produces
  a ``chapter_result`` dict.
- The module-level ``run_chapter()`` thin adapter runs ``app.run()`` and extracts
  ``chapter_result`` from ``defs``.
- ``ChapterRegistry._safe_run()`` wraps that dict into ``ExampleResult`` (oracle).

This module MUST NOT depend on marimo so that ``just examples`` / pytest /
interactive mode stay in sync.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

_ORACLE_KIND = "oracle"
_PASS_MARK = chr(0x2705)
_FAIL_MARK = chr(0x274C)


def make_chapter_result(
    *,
    passed: bool,
    summary: str,
    details: dict[str, Any] | None = None,
    kind: str = _ORACLE_KIND,
) -> dict[str, Any]:
    """Assemble the standard ``chapter_result`` dict (``{"passed", "summary", "details"}``).

    Args:
        passed: Whether the chapter oracle passed.
        summary: One-line readable summary (shown by headless runner / pytest).
        details: Structured details rendered by ``details_to_rows()`` as notebook table rows.
        kind: Result kind, default ``"oracle"`` (aligned with ``ExampleResult.kind``).
    """
    return {
        "passed": bool(passed),
        "kind": str(kind),
        "summary": str(summary),
        "details": details,
    }


def render_checks(checks: Mapping[str, bool], *, printer: Any = print) -> None:
    """Print the assertion checklist line by line (visually marked).

    Assertion expansion should live in its own cell; keep assertions idempotent
    across interactive re-runs (e.g. server-side "exists-match" semantics).
    """
    for name, ok in checks.items():
        printer(f"{name!s:>36}: {_PASS_MARK if bool(ok) else _FAIL_MARK}")


def checks_passed(checks: Mapping[str, bool]) -> bool:
    """Aggregate the checklist: all items must pass."""
    return bool(checks) and all(bool(ok) for ok in checks.values())
