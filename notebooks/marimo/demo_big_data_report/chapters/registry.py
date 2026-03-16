from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult


def all_chapter_ids() -> List[str]:
    return list(_ALL_CHAPTER_IDS)


_ALL_CHAPTER_IDS = [
    "basics",
    "yaml_dsl",
    "workflow_yaml",
    "sinks",
    "memory_opt",
    "observability",
    "parallel_mode",
    "diagnostics",
    "guardrails",
    "loader_retry",
    "output_composition",
    "derived_set_aggregations",
    # `public API` 覆盖章节(并入主线; `deterministic`)
    "public_api_dsl_by_yaml",
    "public_api_spec_ir",
    "public_api_planning",
    "public_api_execution",
    "public_api_ob",
    "public_api_hooks_events",
]


@dataclass(frozen=True)
class _Case:
    chapter_id: str
    run: Callable[[], ExampleResult]


def _load_case(chapter_id: str) -> _Case:
    mod = importlib.import_module(f"notebooks.marimo.demo_big_data_report.chapters.{chapter_id}")
    run_fn_name = "run_{}".format(chapter_id)
    run = getattr(mod, run_fn_name, None)
    if run is None:
        run = getattr(mod, "run_chapter", None)
    if run is None:
        run = getattr(mod, "run", None)
    if run is None or not callable(run):
        msg = "missing callable `{}` (or `run_chapter()`/`run()`) in chapter module: {}".format(run_fn_name, mod.__name__)
        raise AttributeError(msg)
    return _Case(chapter_id=chapter_id, run=run)


def _safe_run(case: _Case) -> ExampleResult:
    example_id = f"demo_big_data_report/{case.chapter_id}"
    try:
        result = case.run()
    except Exception as exc:  # noqa: BLE001
        return ExampleResult(
            example_id=example_id,
            passed=False,
            kind=EXAMPLE_KIND_ORACLE,
            summary="{}: {}".format(type(exc).__name__, exc),
            details={"exc_type": type(exc).__name__, "message": str(exc)},
        )
    if result.example_id != example_id:
        return ExampleResult(
            example_id=example_id,
            passed=False,
            kind=result.kind or EXAMPLE_KIND_ORACLE,
            summary="mismatched example_id: {} != {}".format(result.example_id, example_id),
            details={"returned_example_id": result.example_id},
        )
    return result


def run_selected_chapters(*, chapter_ids: Sequence[str], slow_ok: bool = False) -> List[ExampleResult]:
    _ = slow_ok
    wanted = list(chapter_ids)
    unknown = sorted(set(wanted) - set(_ALL_CHAPTER_IDS))
    if unknown:
        msg = "unknown chapter_ids: {} (known: {})".format(", ".join(unknown), ", ".join(_ALL_CHAPTER_IDS))
        raise ValueError(msg)
    cases = [_load_case(chapter_id) for chapter_id in wanted]
    return [_safe_run(case) for case in cases]


def run_all_chapters(*, slow_ok: bool = False) -> List[ExampleResult]:
    return run_selected_chapters(chapter_ids=_ALL_CHAPTER_IDS, slow_ok=slow_ok)


def iter_chapters() -> Iterable[str]:
    return tuple(_ALL_CHAPTER_IDS)


def get_chapter_module_name(chapter_id: str) -> str:
    if chapter_id not in _ALL_CHAPTER_IDS:
        msg = "unknown chapter_id: {}".format(chapter_id)
        raise KeyError(msg)
    return f"notebooks.marimo.demo_big_data_report.chapters.{chapter_id}"


def find_first_failure(results: Sequence[ExampleResult]) -> Optional[ExampleResult]:
    return next((r for r in results if not r.passed), None)
