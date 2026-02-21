from __future__ import annotations

from pathlib import Path

import pytest

import scalim.execution.run_ir as run_ir_mod
from scalim.execution.run_ir import ExecutionRequest, ExportLayout, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.hooks.base import BaseHook
from scalim.ob.components import split_components
from scalim.sinks.sink_csv import ColumnCSVSink
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryListSink
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import MainSourceIr


def test_tee_row_sink_write_row_writes_to_both_sinks() -> None:
    primary = InMemoryListSink()
    secondary = InMemoryListSink()
    tee = run_ir_mod._TeeRowSink(primary, secondary)  # noqa: SLF001

    tee.write_row({"id": 1})
    tee.close()

    assert primary.get_data() == [{"id": 1}]
    assert secondary.get_data() == [{"id": 1}]


def test_wrap_sink_for_row_count_column_sink_delegates_write_column() -> None:
    tracker = run_ir_mod.InternalStatsCollector()
    underlying = InMemoryColumnSink(field_names=["id"])

    wrapped = run_ir_mod._wrap_sink_for_row_count(underlying, tracker)  # noqa: SLF001
    wrapped.set_row_ids([1, 2])  # type: ignore[attr-defined]
    wrapped.write_column("id", {1: 1, 2: 2})  # type: ignore[attr-defined]

    assert underlying.get_columns()["id"][1] == 1


def test_get_field_name_returns_field_id_when_name_equals_field_id() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    field = FieldIr(field_id="order_id", name="order_id", source=main_source)
    assert run_ir_mod._get_field_name("order_id", field) == "order_id"  # noqa: SLF001


def test_export_layout_from_demand_ir_default_header_field_id_mode_has_no_header_names() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )

    layout = export_layout_from_demand_ir(demand_ir, ["order_id"])
    assert layout.header_names is None


def test_export_layout_from_demand_ir_name_mode_returns_none_when_name_map_empty() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="order_id", source=main_source)], main_source=main_source
    )

    layout = export_layout_from_demand_ir(demand_ir, ["order_id"], header_fields_output_by="name")
    assert layout.header_names is None


def test_create_file_sink_supports_csv_column_mode(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    layout = ExportLayout(field_ids=("id",), header_names=("ID",))

    sink = run_ir_mod._create_file_sink(OutputSpec(format="csv", path=str(output_path), streaming=False), layout)  # noqa: SLF001
    assert isinstance(sink, ColumnCSVSink)
    sink.close()
    assert output_path.exists()


def test_create_output_plan_returns_file_sink_when_no_sink_provided(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    layout = ExportLayout(field_ids=("id",), header_names=None)

    output_plan = run_ir_mod._create_output_plan(OutputSpec(format="csv", path=str(output_path), streaming=True), layout, None)  # noqa: SLF001
    assert output_plan.output_path == str(output_path)
    output_plan.sink.close()
    assert output_path.exists()


def test_create_output_plan_builds_tee_row_sink_and_delegates_write_row(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    layout = ExportLayout(field_ids=("id",), header_names=None)
    secondary = InMemoryListSink()

    output_plan = run_ir_mod._create_output_plan(OutputSpec(format="csv", path=str(output_path), streaming=True), layout, secondary)  # noqa: SLF001
    output_plan.sink.write_row({"id": 1})  # type: ignore[attr-defined]
    output_plan.sink.close()

    assert secondary.get_data() == [{"id": 1}]
    assert output_path.exists()


def test_run_ir_registers_hooks_from_components() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )

    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=None,
        components=[BaseHook()],
    )
    result = run_ir(demand_ir, request)
    assert result.total_rows == 0


def test_split_components_accepts_hook_and_rejects_invalid_component() -> None:
    observers, hooks = split_components([BaseHook()])
    assert observers == ()
    assert hooks

    with pytest.raises(TypeError, match="Invalid component"):
        _ = split_components([object()])
