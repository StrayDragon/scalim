from __future__ import absolute_import

from typing import Dict, Optional, Sequence, Tuple

from ...sinks import BaseRowSink, CSVSink, ExcelSink, ExcelWorkbookSink, IRowSink
from ...typedefs import RowData
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from ..managed_artifacts import ManagedArtifactPlan, create_managed_artifact_sink
from ..output_contracts import ExportLayout, OutputSpec


@dataclass
class RowCounter:
    rows: int = 0


class _CountingOutputRowSink(BaseRowSink):
    _sink: IRowSink
    _counter: RowCounter

    def __init__(self, sink: IRowSink, counter: RowCounter) -> None:
        self._sink = sink
        self._counter = counter

    @override
    def write_row(self, row: RowData) -> None:
        self._counter.rows += 1
        self._sink.write_row(row)

    @override
    def write_batch(self, rows: Sequence[RowData]) -> None:
        self._counter.rows += len(rows)
        self._sink.write_batch(rows)

    @override
    def close(self) -> None:
        self._sink.close()


def _create_csv_sink(output: OutputSpec, layout: ExportLayout) -> CSVSink:
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    return CSVSink(
        output_path=str(output.path),
        encoding=str(output.encoding),
        field_names=field_names,
        header_names=header_names,
        include_header=bool(output.include_header),
        flush_policy="every_n_rows",
    )


def _create_excel_row_sink(output: OutputSpec, layout: ExportLayout) -> IRowSink:
    field_names = list(layout.field_ids)
    header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
    sheet_name = str(output.sheet_name) if output.sheet_name else "Sheet1"
    return ExcelSink(
        output_path=str(output.path),
        field_names=field_names,
        header_names=header_names,
        sheet_name=sheet_name,
        include_header=bool(output.include_header),
        allow_formulas=bool(output.excel_allow_formulas),
    )


def get_or_create_excel_workbook_sink(
    output: OutputSpec,
    *,
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
) -> "ExcelWorkbookSink":
    path = str(output.path)
    wb = workbook_by_path.get(path)
    if wb is None:
        wb = ExcelWorkbookSink(path)
        workbook_by_path[path] = wb
    return wb


def create_row_sink_for_composed_output(
    *,
    target_id: str,
    output: OutputSpec,
    layout: ExportLayout,
    workbook_by_path: Dict[str, "ExcelWorkbookSink"],
    in_memory: bool = False,
    managed_artifact_kind: Optional[str] = None,
) -> Tuple[IRowSink, RowCounter, Optional[ManagedArtifactPlan]]:
    fmt = (output.format or "csv").lower()
    if not output.path and not in_memory:
        msg = "OutputSpec.path is required for composed outputs (target_id={}, format={})".format(target_id, fmt)
        raise ValueError(msg)

    if in_memory:
        counter = RowCounter()
        managed_sink, managed_plan = create_managed_artifact_sink(
            target_id=str(target_id),
            fmt=str(fmt),
            layout=layout,
            output=output,
            managed_artifact_kind=managed_artifact_kind,
        )
        sink = _CountingOutputRowSink(managed_sink, counter)
        return sink, counter, managed_plan

    if fmt == "csv":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for csv (streaming=true)"
            raise ValueError(msg)
        counter = RowCounter()
        sink = _CountingOutputRowSink(_create_csv_sink(output, layout), counter)
        return sink, counter, None

    if fmt == "excel":
        if not output.streaming:
            msg = "Composed outputs only support streaming row sinks for excel (streaming=true)"
            raise ValueError(msg)

        counter = RowCounter()
        if output.sheet_name:
            wb = get_or_create_excel_workbook_sink(output, workbook_by_path=workbook_by_path)
            field_names = list(layout.field_ids)
            header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
            sheet_sink = wb.create_sheet_row_sink(
                str(output.sheet_name),
                field_names=field_names,
                header_names=header_names,
                include_header=bool(output.include_header),
                allow_formulas=bool(output.excel_allow_formulas),
            )
            sink = _CountingOutputRowSink(sheet_sink, counter)
            return sink, counter, None

        # 单工作表 `Excel` 输出(独立文件)
        sink = _CountingOutputRowSink(_create_excel_row_sink(output, layout), counter)
        return sink, counter, None

    msg = "Unsupported output format for composed outputs: {!r}".format(output.format)
    raise ValueError(msg)
