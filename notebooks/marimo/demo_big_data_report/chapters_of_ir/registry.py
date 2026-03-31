from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from scalim_misc.examples._types import ExampleResult
from scalim_misc.notebook_support import ChapterRegistry

_REGISTRY = ChapterRegistry(
    registry_file=__file__,
    module_name_prefix="notebooks.marimo.demo_big_data_report.chapters_of_ir",
    example_id_prefix="demo_big_data_report",
    chapter_file_pattern=r"^(ch\d+_[a-z][a-z0-9_]+)\.py$",
    run_resolver="allow_unique_run",
)


def all_chapter_ids() -> List[str]:
    return _REGISTRY.all_chapter_ids()


def run_selected_chapters(*, chapter_ids: Sequence[str], slow_ok: bool = False) -> List[ExampleResult]:
    return _REGISTRY.run_selected_chapters(chapter_ids=chapter_ids, slow_ok=slow_ok)


def run_all_chapters(*, slow_ok: bool = False) -> List[ExampleResult]:
    return _REGISTRY.run_all_chapters(slow_ok=slow_ok)


def iter_chapters() -> Iterable[str]:
    return _REGISTRY.iter_chapters()


def get_chapter_module_name(chapter_id: str) -> str:
    return _REGISTRY.get_chapter_module_name(chapter_id)


def find_first_failure(results: Sequence[ExampleResult]) -> Optional[ExampleResult]:
    return _REGISTRY.find_first_failure(results)
