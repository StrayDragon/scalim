"""Scalim `demo_big_data_report` 教程章节(可被 `marimo` 与集成对拍运行器复用)."""

from ._types import ChapterResult
from .registry import run_all_chapters

__all__ = [
    "ChapterResult",
    "run_all_chapters",
]
