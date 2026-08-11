"""OutputWriteLayout resolve + factory mapping tests."""

from pathlib import Path

import importlib

import pytest

from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, OutputWriteLayout
from scalim.execution import ExcelColumnResidency, ExecutionRequest, ExportLayout, OutputSpec
from scalim.execution.output_composition import OutputCompositionSpec, OutputTargetSpec
from scalim.execution.output_write_layout import resolve_output_write_layout
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.sinks import CSVSink, ColumnCSVSink, ColumnExcelSink, ExcelSink, StreamingColumnExcelSink
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

run_ir_mod = importlib.import_module("scalim.execution.run_ir")


@pytest.mark.parametrize(
    "streaming,fmt,residency,expected",
    [
        (True, "csv", ExcelColumnResidency.HOLD, OutputWriteLayout.ROW_STREAM),
        (True, "excel", ExcelColumnResidency.HOLD, OutputWriteLayout.ROW_STREAM),
        (False, "csv", ExcelColumnResidency.HOLD, OutputWriteLayout.COLUMN_HOLD),
        (False, "csv", ExcelColumnResidency.WINDOW, OutputWriteLayout.COLUMN_HOLD),
        (False, "excel", ExcelColumnResidency.HOLD, OutputWriteLayout.COLUMN_HOLD),
        (False, "excel", ExcelColumnResidency.WINDOW, OutputWriteLayout.COLUMN_WINDOW),
    ],
)
def test_resolve_derives_legacy_table(streaming, fmt, residency, expected) -> None:
    got = resolve_output_write_layout(
        output_write_layout=None,
        streaming=streaming,
        output_format=fmt,
        excel_column_residency=residency,
        has_output_composition=False,
    )
    assert got is expected


def test_resolve_composition_forces_row_stream() -> None:
    got = resolve_output_write_layout(
        output_write_layout=None,
        streaming=False,
        output_format="excel",
        excel_column_residency=ExcelColumnResidency.HOLD,
        has_output_composition=True,
    )
    assert got is OutputWriteLayout.ROW_STREAM


def test_explicit_layout_wins() -> None:
    got = resolve_output_write_layout(
        output_write_layout=OutputWriteLayout.COLUMN_HOLD,
        streaming=True,
        output_format="excel",
        excel_column_residency=ExcelColumnResidency.WINDOW,
        has_output_composition=False,
    )
    assert got is OutputWriteLayout.COLUMN_HOLD


def test_resolve_rejects_non_enum_layout() -> None:
    with pytest.raises(TypeError, match="output_write_layout must be an OutputWriteLayout"):
        resolve_output_write_layout(
            output_write_layout="column_hold",  # type: ignore[arg-type]
            streaming=False,
            output_format="excel",
            excel_column_residency=ExcelColumnResidency.HOLD,
            has_output_composition=False,
        )


def test_options_reject_string_layout() -> None:
    with pytest.raises(TypeError, match="OutputWriteLayout"):
        _ = DemandRunRuntimeOptions(output_write_layout="row_stream")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="OutputWriteLayout"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=("a",)),
            output_write_layout="column_hold",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "streaming,fmt,residency,sink_type",
    [
        (True, "csv", ExcelColumnResidency.HOLD, CSVSink),
        (False, "csv", ExcelColumnResidency.HOLD, ColumnCSVSink),
        (False, "csv", ExcelColumnResidency.WINDOW, ColumnCSVSink),
        (True, "excel", ExcelColumnResidency.HOLD, ExcelSink),
        (False, "excel", ExcelColumnResidency.HOLD, ColumnExcelSink),
        (False, "excel", ExcelColumnResidency.WINDOW, StreamingColumnExcelSink),
    ],
)
def test_unset_layout_preserves_legacy_sink_types(tmp_path: Path, streaming, fmt, residency, sink_type) -> None:
    layout = ExportLayout(field_ids=("id",))
    ext = "csv" if fmt == "csv" else "xlsx"
    sink = run_ir_mod._create_file_sink(
        OutputSpec(format=fmt, path=str(tmp_path / ("out." + ext)), streaming=streaming),
        layout,
        excel_column_residency=residency,
        output_write_layout=None,
    )
    assert isinstance(sink, sink_type)
    if isinstance(sink, StreamingColumnExcelSink):
        with pytest.raises(RuntimeError, match="set_row_ids"):
            sink.close()
    else:
        sink.close()


def test_explicit_csv_column_window_fails_fast(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="column_window"):
        _ = run_ir_mod._create_file_sink(
            OutputSpec(format="csv", path=str(tmp_path / "x.csv"), streaming=False),
            ExportLayout(field_ids=("id",)),
            output_write_layout=OutputWriteLayout.COLUMN_WINDOW,
        )


def test_composition_plus_explicit_column_layout_fails_fast(tmp_path: Path) -> None:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    runtime_bindings = RuntimeBindings(main_source_loaders={"orders": (lambda: [{"id": 1}])})
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="id", name="ID", source=main_source)],
        main_source=main_source,
    )
    composition = OutputCompositionSpec(
        targets=(
            OutputTargetSpec(
                target_id="t1",
                layout=ExportLayout(field_ids=("id",)),
                output=OutputSpec(format="excel", path=str(tmp_path / "out.xlsx"), streaming=True),
            ),
        ),
    )
    req = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("id",)),
        output_composition=composition,
        runtime_bindings=runtime_bindings,
        output_write_layout=OutputWriteLayout.COLUMN_HOLD,
    )
    with pytest.raises(ValueError, match="output_composition"):
        _ = run_ir_mod.run_ir(demand_ir, req)


def test_explicit_column_window_selects_streaming_column_excel(tmp_path: Path) -> None:
    layout = ExportLayout(field_ids=("id",))
    sink = run_ir_mod._create_file_sink(
        OutputSpec(format="excel", path=str(tmp_path / "w.xlsx"), streaming=True),
        layout,
        excel_column_residency=ExcelColumnResidency.HOLD,
        output_write_layout=OutputWriteLayout.COLUMN_WINDOW,
    )
    assert isinstance(sink, StreamingColumnExcelSink)
    with pytest.raises(RuntimeError, match="set_row_ids"):
        sink.close()
