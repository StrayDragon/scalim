"""`YAML` `DSL` 官方入口.

普通用户建议仅从此处导入最常用的运行入口与运行期契约,避免误用内部实现细节.
"""

from typing import TYPE_CHECKING, Any

from ...vendor.compact.importlibx import import_module
from .runtime.contracts import (
    UNSET,
    Compilation,
    OutputOverrides,
    ResolverTrustedMode,
    RunOverrides,
    RunResult,
)

if TYPE_CHECKING:
    from .runtime.entrypoints import compile as compile  # noqa: A004
    from .runtime.entrypoints import run as run
    from .workflow_entrypoints import run_workflow as run_workflow
else:

    def compile(*args: Any, **kwargs: Any) -> Compilation:  # noqa: A001
        entrypoints = import_module("scalim.dsl.by_yaml.runtime.entrypoints")
        return entrypoints.compile(*args, **kwargs)

    def run(*args: Any, **kwargs: Any) -> RunResult:
        entrypoints = import_module("scalim.dsl.by_yaml.runtime.entrypoints")
        return entrypoints.run(*args, **kwargs)

    def run_workflow(*args: Any, **kwargs: Any) -> Any:
        entrypoints = import_module("scalim.dsl.by_yaml.workflow_entrypoints")
        return entrypoints.run_workflow(*args, **kwargs)


__all__ = (
    "UNSET",
    "Compilation",
    "OutputOverrides",
    "ResolverTrustedMode",
    "RunOverrides",
    "RunResult",
    "compile",
    "run",
    "run_workflow",
)
