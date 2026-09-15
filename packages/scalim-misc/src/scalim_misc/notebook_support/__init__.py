"""Helpers for Marimo notebooks and headless examples.

This package MUST NOT depend on `marimo` so it can be safely imported by:
- `just examples`
- pytest
"""

from .cell_source import extract_visible_cell_sources
from .chapter_result import checks_passed, make_chapter_result, render_checks
from .chapters_registry import ChapterRegistry
from .counting_sink import CountingRowSink
from .pathing import (
    demo_big_data_report_declared_yaml_dsl_dir,
    demo_big_data_report_dir,
    demo_big_data_report_workflow_yaml_path,
    demo_big_data_report_yaml_path,
    ensure_repo_root_on_sys_path,
    find_repo_root,
)
from .results_view import details_to_rows
from .rss_proxy import measure_rss_delta_kb, rss_kb
from .yaml_excerpt import excerpt_by_regex, excerpt_head

__all__ = [
    "ChapterRegistry",
    "CountingRowSink",
    "checks_passed",
    "demo_big_data_report_declared_yaml_dsl_dir",
    "demo_big_data_report_dir",
    "demo_big_data_report_workflow_yaml_path",
    "demo_big_data_report_yaml_path",
    "details_to_rows",
    "ensure_repo_root_on_sys_path",
    "excerpt_by_regex",
    "excerpt_head",
    "extract_visible_cell_sources",
    "find_repo_root",
    "make_chapter_result",
    "measure_rss_delta_kb",
    "render_checks",
    "rss_kb",
]
