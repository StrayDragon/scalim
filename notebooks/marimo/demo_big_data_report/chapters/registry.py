from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult


_CHAPTER_FILE_RE = re.compile(r"^(ch\d{3}_[a-z0-9_]+)\.py$")


def _discover_chapter_modules() -> List[Tuple[str, str]]:
    chapters_dir = Path(__file__).resolve().parent
    found: List[Tuple[str, str]] = []
    for path in chapters_dir.iterdir():
        if not path.is_file():
            continue
        match = _CHAPTER_FILE_RE.match(path.name)
        if not match:
            continue
        chapter_id = match.group(1)
        module_name = "notebooks.marimo.demo_big_data_report.chapters.{}".format(path.stem)
        found.append((chapter_id, module_name))
    return sorted(found, key=lambda item: item[0])


_CHAPTERS = _discover_chapter_modules()
_CHAPTER_MODULES_BY_ID: Dict[str, str] = dict(_CHAPTERS)


def all_chapter_ids() -> List[str]:
    return list(_ALL_CHAPTER_IDS)


_ALL_CHAPTER_IDS = [chapter_id for chapter_id, _module_name in _CHAPTERS]


@dataclass(frozen=True)
class _Case:
    chapter_id: str
    run: Callable[[], ExampleResult]


def _load_case(chapter_id: str) -> _Case:
    mod = importlib.import_module(_CHAPTER_MODULES_BY_ID[chapter_id])
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
    return _CHAPTER_MODULES_BY_ID[chapter_id]


def find_first_failure(results: Sequence[ExampleResult]) -> Optional[ExampleResult]:
    return next((r for r in results if not r.passed), None)
