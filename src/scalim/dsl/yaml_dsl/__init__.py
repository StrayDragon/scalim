"""`YAML` `DSL` 官方入口.

普通用户建议仅从此处导入最常用的运行入口与运行期契约,避免误用内部实现细节.
"""

from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional

from ...vendor.compact.importlibx import import_module
from .runtime.contracts import (
    UNSET,
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    Compilation,
    DemandDiagnosticsOverride,
    DemandDiagnosticsPolicy,
    FileResourceOverride,
    OutputDefaultsToOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResolverTrustedMode,
    ResourcesOverride,
    RunOptions,
    RunOverrides,
    RunResult,
)

if TYPE_CHECKING:
    from ...workflow.report import WorkflowResult
    from .runtime.entrypoints import compile as compile  # noqa: A004
    from .runtime.entrypoints import run as run
    from .workflow_entrypoints import run_workflow as run_workflow
    from .workflow_types import WorkflowRunOptionsPatch, WorkflowRuntimeOptions
else:

    def compile(yaml_path: str, *, options: RunOptions) -> Compilation:  # noqa: A001
        entrypoints = import_module("scalim.dsl.yaml_dsl.runtime.entrypoints")
        return entrypoints.compile(yaml_path, options=options)

    def run(yaml_path: str, *, options: RunOptions) -> RunResult:
        entrypoints = import_module("scalim.dsl.yaml_dsl.runtime.entrypoints")
        return entrypoints.run(yaml_path, options=options)

    def run_workflow(
        workflow_yaml_path: str,
        *,
        options: RunOptions,
        run_options_patches_by_run_id: Optional[Mapping[str, "WorkflowRunOptionsPatch"]] = None,
        workflow_runtime_options: Optional["WorkflowRuntimeOptions"] = None,
        path_aliases: Optional[Mapping[str, str]] = None,
        run_ir_fn: Optional[Callable[..., Any]] = None,
        compile_demand_yaml_fn: Optional[Callable[..., Any]] = None,
    ) -> "WorkflowResult":
        entrypoints = import_module("scalim.dsl.yaml_dsl.workflow_entrypoints")
        return entrypoints.run_workflow(
            workflow_yaml_path,
            options=options,
            run_options_patches_by_run_id=run_options_patches_by_run_id,
            workflow_runtime_options=workflow_runtime_options,
            path_aliases=path_aliases,
            run_ir_fn=run_ir_fn,
            compile_demand_yaml_fn=compile_demand_yaml_fn,
        )


__all__ = (
    "UNSET",
    "BookBudgetOverride",
    "BookExportXlsxOverride",
    "BookResourceOverride",
    "BookWriteDefaultsOverride",
    "Compilation",
    "DemandDiagnosticsOverride",
    "DemandDiagnosticsPolicy",
    "FileResourceOverride",
    "OutputDefaultsToOverride",
    "OutputExtraSheetOverride",
    "OutputExtrasOverride",
    "OutputOverride",
    "OutputToOverride",
    "OutputWriteOverride",
    "OutputsDefaultsOverride",
    "ResolverTrustedMode",
    "ResourcesOverride",
    "RunOptions",
    "RunOverrides",
    "RunResult",
    "compile",
    "run",
    "run_workflow",
)
