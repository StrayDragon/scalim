"""`scalim_misc.examples`: notebooks/examples gate shared helpers.

说明:
- `notebooks/marimo/` 是教学入口 + SSOT 执行入口
- 本包仅保留 headless 复用的“结果结构 + runner 工具函数”
"""

from ._types import EXAMPLE_KIND_FIXTURE, EXAMPLE_KIND_ORACLE, EXAMPLE_KIND_SMOKE, ExampleResult
from .harness import exit_code, format_results, summarize_failures

__all__ = [
    "EXAMPLE_KIND_FIXTURE",
    "EXAMPLE_KIND_ORACLE",
    "EXAMPLE_KIND_SMOKE",
    "ExampleResult",
    "exit_code",
    "format_results",
    "summarize_failures",
]
