"""`YAML` `DSL` 官方入口.

普通用户建议仅从此处导入最常用的运行入口与运行期契约,避免误用内部实现细节.
"""

# pragma: scalim-public-api tier1:10:scalim.dsl.yaml_dsl|YAML DSL 官方运行入口 + 运行期契约|运行 demand/workflow YAML
# pragma: scalim-public-api tier1:20:scalim.dsl.yaml_dsl.tools|YAML DSL 辅助工具(输出配置/路径推导)|工具链集成/排错
# pragma: scalim-public-api tier1:30:scalim.dsl.yaml_dsl.workflow|workflow 配置(稳定导入路径)|解析/校验 workflow YAML
# pragma: scalim-public-api tier1:40:scalim.dsl.yaml_dsl.workflow_types|workflow 类型(拆分给 typing/依赖方用)|仅用类型,或避免重导入
# pragma: scalim-public-api tier1:50:scalim.dsl.yaml_dsl.workflow_paths|workflow 路径解析(稳定导入路径)|解析 workflow 引用的 demand 路径

from typing import TYPE_CHECKING

from ...execution.excel_column_residency import ExcelColumnResidency
from ...vendor.compact.importlibx import import_module
from .book_resource_policy import (
    BookResourcePolicy,
    BookWriteAlignBy,
    BookWriteHeaderPolicy,
    BookWriteMode,
    BookWriteOnConflict,
    BookWriteOnMismatch,
    BookWritePolicy,
    ResourcesPolicy,
)
from .runtime.contracts import (
    UNSET,
    BookExportXlsxOverride,
    BookResourceOverride,
    CaptureNone,
    CapturePolicy,
    CaptureRows,
    Compilation,
    DemandDiagnosticsOverride,
    DemandDiagnosticsPolicy,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunResult,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    FileResourceOverride,
    LookupChunking,
    OutputDefaultsToOverride,
    OutputExtraSheetOverride,
    OutputExtrasOverride,
    OutputOverride,
    OutputsDefaultsOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResolverTrustedMode,
    ResourcesOverride,
    RowsReuse,
    RunOverrides,
    SourceCache,
)
from .workflow_types import WorkflowRunOptions

if TYPE_CHECKING:
    from ...workflow.report import WorkflowResult
    from .runtime.entrypoints import compile as compile  # noqa: A004
    from .runtime.entrypoints import run as run
    from .workflow_entrypoints import run_workflow as run_workflow
else:

    def compile(yaml_path: str, *, options: DemandRunOptions) -> Compilation:  # noqa: A001
        entrypoints = import_module("scalim.dsl.yaml_dsl.runtime.entrypoints")
        return entrypoints.compile(yaml_path, options=options)

    def run(yaml_path: str, *, options: DemandRunOptions) -> DemandRunResult:
        entrypoints = import_module("scalim.dsl.yaml_dsl.runtime.entrypoints")
        return entrypoints.run(yaml_path, options=options)

    def run_workflow(
        workflow_yaml_path: str,
        *,
        options: WorkflowRunOptions,
    ) -> "WorkflowResult":
        entrypoints = import_module("scalim.dsl.yaml_dsl.workflow_entrypoints")
        return entrypoints.run_workflow(
            workflow_yaml_path,
            options=options,
        )


__all__ = (
    "UNSET",
    "BookExportXlsxOverride",
    "BookResourceOverride",
    "BookResourcePolicy",
    "BookWriteAlignBy",
    "BookWriteHeaderPolicy",
    "BookWriteMode",
    "BookWriteOnConflict",
    "BookWriteOnMismatch",
    "BookWritePolicy",
    "CaptureNone",
    "CapturePolicy",
    "CaptureRows",
    "Compilation",
    "DemandDiagnosticsOverride",
    "DemandDiagnosticsPolicy",
    "DemandRunOptions",
    "DemandRunOutputOptions",
    "DemandRunResult",
    "DemandRunRuntimeOptions",
    "DemandRunSecurityOptions",
    "DemandRunTemplateOptions",
    "ExcelColumnResidency",
    "FileResourceOverride",
    "LookupChunking",
    "OutputDefaultsToOverride",
    "OutputExtraSheetOverride",
    "OutputExtrasOverride",
    "OutputOverride",
    "OutputToOverride",
    "OutputWriteOverride",
    "OutputsDefaultsOverride",
    "ResolverTrustedMode",
    "ResourcesOverride",
    "ResourcesPolicy",
    "RowsReuse",
    "RunOverrides",
    "SourceCache",
    "WorkflowRunOptions",
    "compile",
    "run",
    "run_workflow",
)
