"""执行层入口(稳定导入路径)."""

# pragma: scalim-public-api tier1:90:scalim.execution|execution facade(run_ir + contracts)|DSL-agnostic 执行入口 + request/result 契约

from .excel_column_residency import ExcelColumnResidency
from .output_write_layout import OutputWriteLayout, resolve_output_write_layout
from .run_ir import (
    ExecutionRequest,
    ExecutionResult,
    ExportLayout,
    ObservabilitySpec,
    OutputSpec,
    export_layout_from_demand_ir,
    run_ir,
)

__all__ = (
    "ExcelColumnResidency",
    "ExecutionRequest",
    "ExecutionResult",
    "ExportLayout",
    "ObservabilitySpec",
    "OutputSpec",
    "OutputWriteLayout",
    "export_layout_from_demand_ir",
    "resolve_output_write_layout",
    "run_ir",
)
