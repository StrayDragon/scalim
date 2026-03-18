from pathlib import Path

import pytest

import scalim.execution.run_ir as run_ir_mod
from scalim.execution.run_ir import ExecutionRequest, ExportLayout, ObservabilitySpec, OutputSpec, export_layout_from_demand_ir, run_ir
from scalim.ob.observer import Observer
from scalim.ob.presets.viz import VizObserverConfig
from scalim.sinks.sink_base import BaseRowSink, BaseSink, IColumnSink, IRowSink
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryListSink, InMemoryRowSink
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import MainSourceIr
from scalim.vendor.compact.typing_extensionsx import override


def test_run_ir_dunder_all_excludes_internal_stats_collector() -> None:
    assert "InternalStatsCollector" not in run_ir_mod.__all__


def test_export_layout_rejects_misaligned_header_names() -> None:
    with pytest.raises(ValueError, match="header_names"):
        _ = ExportLayout(field_ids=("a",), header_names=("A", "B"))


def test_tee_row_sink_write_batch_writes_to_both_sinks() -> None:
    primary = InMemoryListSink()
    secondary = InMemoryListSink()
    tee = run_ir_mod._TeeRowSink(primary, secondary)  # noqa: SLF001

    tee.write_batch([{"id": 1}, {"id": 2}])
    tee.close()

    assert primary.get_data() == [{"id": 1}, {"id": 2}]
    assert secondary.get_data() == [{"id": 1}, {"id": 2}]


def test_export_layout_from_demand_ir_skips_unknown_fields_when_building_name_map() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )

    layout = export_layout_from_demand_ir(demand_ir, ["order_id", "missing"], header_fields_output_by="name")
    assert layout.field_ids == ("order_id", "missing")
    assert layout.header_names == ("Order ID", "missing")


def test_create_file_sink_creates_parent_dirs_and_supports_excel(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "out.xlsx"
    layout = ExportLayout(field_ids=("id",), header_names=("ID",))

    sink = run_ir_mod._create_file_sink(  # noqa: SLF001
        OutputSpec(format="excel", path=str(output_path), streaming=True, include_header=True),
        layout,
    )
    assert sink is not None
    assert output_path.parent.exists()
    sink.close()
    assert output_path.exists()


def test_create_file_sink_supports_excel_column_mode(tmp_path: Path) -> None:
    output_path = tmp_path / "out_cols.xlsx"
    layout = ExportLayout(field_ids=("id",), header_names=("ID",))

    sink = run_ir_mod._create_file_sink(  # noqa: SLF001
        OutputSpec(format="excel", path=str(output_path), streaming=False, include_header=True),
        layout,
    )
    assert sink is not None
    sink.close()
    assert output_path.exists()


def test_create_file_sink_rejects_unknown_format(tmp_path: Path) -> None:
    output_path = tmp_path / "out.parquet"
    layout = ExportLayout(field_ids=("id",), header_names=None)

    with pytest.raises(ValueError, match="Unsupported output format"):
        _ = run_ir_mod._create_file_sink(OutputSpec(format="parquet", path=str(output_path)), layout)  # noqa: SLF001


def test_run_ir_registers_viz_observer_and_writes_artifacts(tmp_path: Path) -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )

    events_path = tmp_path / "viz_events.jsonl"
    snapshot_path = tmp_path / "viz_snapshot.json"
    sink = InMemoryListSink()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(),
        sink=sink,
        observability=ObservabilitySpec(viz_config=VizObserverConfig(output_path=str(events_path), snapshot_path=str(snapshot_path))),
    )

    result = run_ir(demand_ir, request)
    assert sink.get_data() == [{"order_id": 1}]
    assert result.total_rows == 1
    assert events_path.exists()
    assert snapshot_path.exists()


def test_run_ir_total_rows_counts_even_without_output_or_sink() -> None:
    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}, {"order_id": 2}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=None,
    )
    result = run_ir(demand_ir, request)
    assert result.total_rows == 2
    assert result.output_path is None


def test_run_ir_closes_sink_on_exception() -> None:
    class _ExplodingSink(BaseRowSink):
        def __init__(self) -> None:
            self.closed = False

        @override
        def write_row(self, row) -> None:  # type: ignore[override]
            _ = row
            raise RuntimeError("boom")

        @override
        def close(self) -> None:
            self.closed = True

    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )
    sink = _ExplodingSink()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
    )

    with pytest.raises(RuntimeError, match="boom"):
        _ = run_ir(demand_ir, request)
    assert sink.closed is True


def test_run_ir_raises_when_sink_close_fails_after_successful_run() -> None:
    class _CloseExplodingSink(BaseRowSink):
        def __init__(self) -> None:
            self.rows = []
            self.closed = False

        @override
        def write_row(self, row) -> None:  # type: ignore[override]
            self.rows.append(dict(row))

        @override
        def close(self) -> None:
            self.closed = True
            raise RuntimeError("close boom")

    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )
    sink = _CloseExplodingSink()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
    )

    with pytest.raises(RuntimeError, match="close boom"):
        _ = run_ir(demand_ir, request)
    assert sink.rows == [{"order_id": 1}]
    assert sink.closed is True


def test_run_ir_suppresses_sink_close_error_when_engine_run_fails() -> None:
    class _ExplodingSink(BaseRowSink):
        def __init__(self) -> None:
            self.closed = False

        @override
        def write_row(self, row) -> None:  # type: ignore[override]
            _ = row
            raise RuntimeError("run boom")

        @override
        def close(self) -> None:
            self.closed = True
            raise RuntimeError("close boom")

    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )
    sink = _ExplodingSink()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
    )

    with pytest.raises(RuntimeError, match="run boom"):
        _ = run_ir(demand_ir, request)
    assert sink.closed is True


def test_create_tee_sink_column_mode_delegates_to_both_sinks() -> None:
    primary = InMemoryColumnSink(field_names=["id"])
    secondary = InMemoryColumnSink(field_names=["id"])

    tee = run_ir_mod._create_tee_sink(primary, secondary)  # noqa: SLF001
    tee.write_batch([{"id": 0}])
    tee.set_row_ids([1, 2])  # type: ignore[attr-defined]
    tee.write_column("id", {1: 1, 2: 2})  # type: ignore[attr-defined]
    tee.write_columns({"id": {3: 3}})  # type: ignore[attr-defined]
    tee.close()

    assert primary.get_columns() == secondary.get_columns()


def test_create_tee_sink_rejects_incompatible_sinks() -> None:
    primary = InMemoryRowSink()
    secondary = InMemoryColumnSink(field_names=["id"])

    with pytest.raises(ValueError, match="Incompatible sinks for tee"):
        _ = run_ir_mod._create_tee_sink(primary, secondary)  # noqa: SLF001


def test_create_output_plan_closes_file_sink_on_incompatible_tee(tmp_path: Path) -> None:
    output_path = tmp_path / "out.csv"
    layout = ExportLayout(field_ids=("id",), header_names=None)
    memory_column_sink = InMemoryColumnSink(field_names=["id"])

    with pytest.raises(ValueError, match="Incompatible sinks for tee"):
        _ = run_ir_mod._create_output_plan(  # noqa: SLF001
            OutputSpec(format="csv", path=str(output_path), streaming=True),
            layout,
            memory_column_sink,
        )

    # If file sink wasn't closed, the temp file would remain un-finalized and `output_path` would not exist.
    assert output_path.exists()


def test_create_output_plan_error_message_classifies_non_row_or_column_sink_as_isink(tmp_path: Path) -> None:
    class _RecordingBatchSink(BaseSink):
        def __init__(self) -> None:
            self.closed = False

        @override
        def write_batch(self, rows) -> None:  # type: ignore[override]
            _ = rows

        @override
        def close(self) -> None:
            self.closed = True

    output_path = tmp_path / "out.csv"
    layout = ExportLayout(field_ids=("id",), header_names=None)
    batch_sink = _RecordingBatchSink()

    with pytest.raises(ValueError, match=r"\(ISink\)"):
        _ = run_ir_mod._create_output_plan(  # noqa: SLF001
            OutputSpec(format="csv", path=str(output_path), streaming=True),
            layout,
            batch_sink,
        )

    assert output_path.exists()
    assert batch_sink.closed is False


def test_run_ir_closes_sink_and_observers_when_engine_init_fails() -> None:
    class _ExplodingEngine:
        def __init__(self, **_kwargs) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("init boom")

    class _CloseTrackingSink(BaseRowSink):
        def __init__(self) -> None:
            self.closed = False

        @override
        def write_row(self, row) -> None:  # type: ignore[override]
            _ = row

        @override
        def close(self) -> None:
            self.closed = True

    class _CloseTrackingObserver(Observer):
        def __init__(self) -> None:
            self.closed = False

        def on_event(self, event) -> None:  # type: ignore[override]
            _ = event

        def close(self) -> None:
            self.closed = True

    main_source = MainSourceIr(source_id="orders", loader=lambda: [{"order_id": 1}])
    demand_ir = DemandIr.from_irs(
        sources=[], fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)], main_source=main_source
    )

    sink = _CloseTrackingSink()
    observer = _CloseTrackingObserver()
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(path=None),
        sink=sink,
        components=[observer],
    )

    with pytest.raises(RuntimeError, match="init boom"):
        _ = run_ir(demand_ir, request, engine_factory=_ExplodingEngine)

    assert sink.closed is True
    assert observer.closed is True


def test_wrap_sink_for_row_count_row_sink_counts_write_batch() -> None:
    tracker = run_ir_mod.InternalStatsCollector()
    underlying = InMemoryRowSink()

    wrapped = run_ir_mod._wrap_sink_for_row_count(underlying, tracker)  # noqa: SLF001
    assert isinstance(wrapped, IRowSink)

    wrapped.write_batch([{"id": 1}, {"id": 2}])
    wrapped.close()

    assert tracker.total_rows == 2
    assert underlying.get_data() == [{"id": 1}, {"id": 2}]


def test_wrap_sink_for_row_count_column_sink_counts_set_row_ids_and_write_columns() -> None:
    tracker = run_ir_mod.InternalStatsCollector()
    underlying = InMemoryColumnSink(field_names=["id"])

    wrapped = run_ir_mod._wrap_sink_for_row_count(underlying, tracker)  # noqa: SLF001
    assert isinstance(wrapped, IColumnSink)

    wrapped.set_row_ids([1, 2])
    wrapped.write_columns({"id": {1: 1, 2: 2}})
    wrapped.write_batch([{"id": 3}, {"id": 4}])
    wrapped.close()

    assert tracker.total_rows == 4


def test_wrap_sink_for_row_count_batch_sink_counts_write_batch_and_close() -> None:
    class _RecordingBatchSink(BaseSink):
        def __init__(self) -> None:
            self.rows = []
            self.closed = False

        @override
        def write_batch(self, rows) -> None:  # type: ignore[override]
            self.rows.extend([dict(item) for item in rows])

        @override
        def close(self) -> None:
            self.closed = True

    tracker = run_ir_mod.InternalStatsCollector()
    underlying = _RecordingBatchSink()

    wrapped = run_ir_mod._wrap_sink_for_row_count(underlying, tracker)  # noqa: SLF001
    assert not isinstance(wrapped, (IRowSink, IColumnSink))

    wrapped.write_batch([{"id": 1}, {"id": 2}])
    wrapped.close()

    assert tracker.total_rows == 2
    assert underlying.rows == [{"id": 1}, {"id": 2}]
    assert underlying.closed is True
