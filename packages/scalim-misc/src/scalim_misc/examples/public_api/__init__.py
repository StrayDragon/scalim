from __future__ import annotations

from typing import Callable, Iterator, Tuple

from .._types import EXAMPLE_KIND_ORACLE, EXAMPLE_KIND_SMOKE, ExampleResult
from .components import run_public_api_components
from .dsl_by_yaml import run_public_api_dsl_by_yaml
from .execution import run_public_api_execution
from .ob import run_public_api_observability
from .planning import run_public_api_planning
from .spec_ir import run_public_api_spec_ir


def iter_public_api_examples() -> Iterator[Tuple[str, str, Callable[[], ExampleResult]]]:
    yield ("public_api/dsl_by_yaml", EXAMPLE_KIND_ORACLE, run_public_api_dsl_by_yaml)
    yield ("public_api/spec_ir", EXAMPLE_KIND_ORACLE, run_public_api_spec_ir)
    yield ("public_api/planning", EXAMPLE_KIND_ORACLE, run_public_api_planning)
    yield ("public_api/execution", EXAMPLE_KIND_ORACLE, run_public_api_execution)
    yield ("public_api/components", EXAMPLE_KIND_ORACLE, run_public_api_components)
    yield ("public_api/ob", EXAMPLE_KIND_SMOKE, run_public_api_observability)


__all__ = [
    "iter_public_api_examples",
]
