from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional, Union

_DEFAULT_MARKERS = ("pyproject.toml", "justfile", ".git")


def find_repo_root(start: Union[str, Path], *, markers: Iterable[str] = _DEFAULT_MARKERS) -> Path:
    """Find the repo root by walking up parents and looking for marker files/dirs."""
    path = Path(start).resolve()
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        for marker in markers:
            if (candidate / marker).exists():
                return candidate
    msg = f"repo root not found from: {path}"
    raise RuntimeError(msg)


def ensure_repo_root_on_sys_path(start: Union[str, Path], *, markers: Iterable[str] = _DEFAULT_MARKERS) -> Path:
    """Ensure repo root is on `sys.path` (useful for relative resource access in notebooks)."""
    repo_root = find_repo_root(start, markers=markers)
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
    return repo_root


def demo_big_data_report_dir(start: Union[str, Path], *, repo_root: Optional[Path] = None) -> Path:
    root = repo_root or find_repo_root(start)
    return root / "notebooks" / "marimo" / "demo_big_data_report"


def demo_big_data_report_yaml_path(start: Union[str, Path], *, repo_root: Optional[Path] = None) -> Path:
    return demo_big_data_report_dir(start, repo_root=repo_root) / "by_yaml_dsl" / "ecommerce_report.yaml"


def demo_big_data_report_workflow_yaml_path(start: Union[str, Path], *, repo_root: Optional[Path] = None) -> Path:
    return demo_big_data_report_dir(start, repo_root=repo_root) / "by_yaml_dsl" / "workflow_fixture.yaml"
