from __future__ import absolute_import

from typing import List, Optional, Sequence, Tuple

from ..exceptions import ScalimExecutionException
from ..sinks.sink_excel import ExcelWorkbookSink
from ..spec.ir.demand import DemandIr
from ..vendor.dataclassesx import replace
from .run_ir import ExecutionRequest, ExecutionResult, OutputSpec, run_ir


class ScalimMultiRootWorkbookRunError(ScalimExecutionException):
    sheet_name: str

    def __init__(self, sheet_name: str, exc: Exception) -> None:
        super(ScalimMultiRootWorkbookRunError, self).__init__("Workbook sheet run failed: {}: {}".format(sheet_name, exc))
        self.sheet_name = str(sheet_name)


def run_multi_root_workbook(
    *,
    output_path: str,
    runs: Sequence[Tuple[str, DemandIr, ExecutionRequest]],
    failure_policy: str = "all_fail",
) -> List[ExecutionResult]:
    """将多个独立 `demand` 依次写入同一 `workbook`(多根数据源 `sheet` 集合).

    规则:
    - 目前不做跨 `demand` 的缓存/复用;每个 `demand` 独立执行.
    - `workbook` 仅作为容器复用,保证 `sheet` 顺序与命名冲突策略.
    - `failure_policy`:
      - `all_fail`(默认): 任一 `sheet` 失败即失败
      - `primary_only`: 失败的 `sheet` 会被跳过,继续执行后续 `sheet`(仍会保存已完成内容)
    """

    policy = str(failure_policy or "all_fail")
    if policy not in ("all_fail", "primary_only"):
        msg = "Unsupported failure_policy: {!r}".format(failure_policy)
        raise ValueError(msg)

    wb = ExcelWorkbookSink(str(output_path))
    results: List[ExecutionResult] = []
    first_error: Optional[Exception] = None

    try:
        for sheet_name, demand_ir, request in runs:
            layout = request.export_layout
            field_names = list(layout.field_ids)
            header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)

            sheet_sink = wb.create_sheet_row_sink(
                str(sheet_name),
                field_names=field_names,
                header_names=header_names,
                include_header=True,
            )
            req = replace(
                request,
                output=OutputSpec(path=None),
                sink=sheet_sink,
                output_composition=None,
            )
            try:
                results.append(run_ir(demand_ir, req))
            except Exception as exc:
                if first_error is None:
                    first_error = exc
                if policy == "all_fail":
                    raise ScalimMultiRootWorkbookRunError(str(sheet_name), exc) from exc
                # `primary_only`: `best-effort` 跳过该 `sheet`
                continue
    finally:
        # 始终保存 `workbook`(原子替换).当 `all_fail` 抛错时也尽量保存已完成内容供诊断.
        wb.close()

    if first_error is not None and policy == "primary_only":
        # `primary_only` 不抛错,但允许调用方在 `result` 层检查.
        return results

    return results


__all__ = [
    "ScalimMultiRootWorkbookRunError",
    "run_multi_root_workbook",
]
