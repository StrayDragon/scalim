"""`scalim_misc.examples`: 可复用的示例/回归套件实现.

说明:
- `notebooks/marimo/` 负责交互与讲解
- 本包负责可运行、可回归、可复用的章节/用例逻辑(供 `just examples` / pytest 复用)
"""

from ._types import EXAMPLE_KIND_FIXTURE, EXAMPLE_KIND_ORACLE, EXAMPLE_KIND_SMOKE, ExampleResult
from .harness import run_public_api_examples

__all__ = [
    "EXAMPLE_KIND_FIXTURE",
    "EXAMPLE_KIND_ORACLE",
    "EXAMPLE_KIND_SMOKE",
    "ExampleResult",
    "run_public_api_examples",
]
