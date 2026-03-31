"""Helpers for Marimo notebooks and headless examples.

This package MUST NOT depend on `marimo` so it can be safely imported by:
- `just examples`
- pytest
"""

from .chapters_registry import ChapterRegistry
from .pathing import (
    demo_big_data_report_dir,
    demo_big_data_report_workflow_yaml_path,
    demo_big_data_report_yaml_path,
    ensure_repo_root_on_sys_path,
    find_repo_root,
)
from .results_view import details_to_rows
from .yaml_excerpt import excerpt_by_regex, excerpt_head

__all__ = [
    "ChapterRegistry",
    "demo_big_data_report_dir",
    "demo_big_data_report_workflow_yaml_path",
    "demo_big_data_report_yaml_path",
    "details_to_rows",
    "ensure_repo_root_on_sys_path",
    "excerpt_by_regex",
    "excerpt_head",
    "find_repo_root",
]
