from pathlib import Path

import importlib

import pytest

from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions, ExcelColumnResidency
from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec
from scalim.execution import excel_column_residency as residency_mod
from scalim.execution.output_composition import OutputCompositionSpec, OutputTargetSpec
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.sinks import ColumnExcelSink, StreamingColumnExcelSink
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

run_ir_mod = importlib.import_module("scalim.execution.run_ir")


def test_excel_column_residency_enum_strict() -> None:
    with pytest.raises(TypeError, match="ExcelColumnResidency"):
        _ = DemandRunRuntimeOptions(excel_column_residency="window")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ExcelColumnResidency"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=("a",)),
            excel_column_residency="hold",  # type: ignore[arg-type]
        )


def test_create_file_sink_hold_and_window(tmp_path: Path) -> None:
    layout = ExportLayout(field_ids=("id",), header_names=("ID",))
    hold_path = tmp_path / "hold.xlsx"
    win_path = tmp_path / "win.xlsx"
    hold = run_ir_mod._create_file_sink(
        OutputSpec(format="excel", path=str(hold_path), streaming=False),
        layout,
        excel_column_residency=ExcelColumnResidency.HOLD,
    )
    win = run_ir_mod._create_file_sink(
        OutputSpec(format="excel", path=str(win_path), streaming=False),
        layout,
        excel_column_residency=ExcelColumnResidency.WINDOW,
    )
    assert isinstance(hold, ColumnExcelSink)
    assert isinstance(win, StreamingColumnExcelSink)
    hold.close()
    # Streaming needs set_row_ids before close; abandon via incomplete close path
    with pytest.raises(RuntimeError, match="set_row_ids"):
        win.close()


def test_window_rejects_streaming_excel(tmp_path: Path) -> None:
    layout = ExportLayout(field_ids=("id",))
    with pytest.raises(ValueError, match="WINDOW"):
        _ = run_ir_mod._create_file_sink(
            OutputSpec(format="excel", path=str(tmp_path / "x.xlsx"), streaming=True),
            layout,
            excel_column_residency=ExcelColumnResidency.WINDOW,
        )


def test_window_with_output_composition_fails_fast(tmp_path: Path) -> None:
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": (lambda: [{"id": 1}])},
    )
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
        excel_column_residency=ExcelColumnResidency.WINDOW,
    )
    with pytest.raises(ValueError, match="output_composition"):
        _ = run_ir_mod.run_ir(demand_ir, req)


def test_run_ir_window_writes_streaming_column_excel(tmp_path: Path) -> None:
    out = tmp_path / "stream.xlsx"
    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    runtime_bindings = RuntimeBindings(
        main_source_loaders={
            "orders": (lambda: [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]),
        },
    )
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[
            FieldIr(field_id="id", name="ID", source=main_source),
            FieldIr(field_id="name", name="Name", source=main_source),
        ],
        main_source=main_source,
    )
    req = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("id", "name"), header_names=("ID", "Name")),
        output=OutputSpec(format="excel", path=str(out), streaming=False, include_header=True),
        runtime_bindings=runtime_bindings,
        excel_column_residency=ExcelColumnResidency.WINDOW,
        batch_size=1,
    )
    result = run_ir_mod.run_ir(demand_ir, req)
    assert result.total_rows == 2
    assert out.exists()
    assert residency_mod.ExcelColumnResidency.WINDOW.value == "window"
