"""c15: sink accept set + opt-in precheck + discard-on-exception."""

from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl import DemandRunRuntimeOptions
from scalim.execution import ExecutionRequest, ExportLayout
from scalim.execution.output_composition.sinks import RowCounter, _CountingOutputRowSink
from scalim.sinks import CSVSink, ColumnCSVSink, ColumnExcelSink, ExcelSink, ExcelWorkbookSink, StreamingColumnExcelSink
from scalim.sinks.accept_types import (
    SinkTypePrecheck,
    ensure_sink_accepted_cell,
    is_csv_accepted_cell,
    is_excel_accepted_cell,
)
from scalim.sinks._internal.accept_types import require_sink_type_precheck


def test_excel_accept_set_covers_field_value_scalars() -> None:
    from datetime import datetime

    assert is_excel_accepted_cell(1)
    assert is_excel_accepted_cell(datetime(2024, 1, 2, 3, 4, 5))
    assert is_excel_accepted_cell(None)
    assert not is_excel_accepted_cell(object())
    assert is_csv_accepted_cell(object())


def test_excel_accept_set_does_not_claim_numpy_datetime64() -> None:
    np = pytest.importorskip("numpy")
    assert not is_excel_accepted_cell(np.datetime64("2024-01-02T03:04:05"))


def test_require_and_ensure_sink_type_helpers() -> None:
    assert require_sink_type_precheck(SinkTypePrecheck.ON, where="t") is SinkTypePrecheck.ON
    with pytest.raises(TypeError, match="must be a SinkTypePrecheck"):
        _ = require_sink_type_precheck("on", where="t")
    assert ensure_sink_accepted_cell(1, field_id="v", sink_name="t", accepted=is_excel_accepted_cell) == 1
    with pytest.raises(TypeError, match="sink type precheck failed"):
        _ = ensure_sink_accepted_cell(object(), field_id="v", sink_name="t", accepted=is_excel_accepted_cell)


def test_sink_type_precheck_enum_strict_on_options() -> None:
    with pytest.raises(TypeError, match="SinkTypePrecheck"):
        _ = DemandRunRuntimeOptions(sink_type_precheck="on")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="SinkTypePrecheck"):
        _ = ExecutionRequest(
            export_layout=ExportLayout(field_ids=("a",)),
            sink_type_precheck="off",  # type: ignore[arg-type]
        )


def test_excel_sink_precheck_off_defers_failure(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    path = tmp_path / "late.xlsx"
    # write_only append may accept some values until save; np.datetime64 fails at append/save
    with pytest.raises((TypeError, ValueError)):
        with ExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.OFF) as sink:
            sink.write_row({"v": np.datetime64("2024-01-02T03:04:05")})
    assert not path.exists()


def test_excel_sink_precheck_on_fails_before_write(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    path = tmp_path / "early.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with ExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
            sink.write_row({"v": np.datetime64("2024-01-02T03:04:05")})
    assert not path.exists()


def test_column_excel_sink_precheck_on_fails_before_write(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    path = tmp_path / "col_early.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with ColumnExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
            sink.set_row_ids([1])
            sink.write_column("v", {1: np.datetime64("2024-01-02T03:04:05")})
    assert not path.exists()


def test_column_excel_sink_precheck_on_accepts_field_value(tmp_path: Path) -> None:
    path = tmp_path / "col_ok.xlsx"
    with ColumnExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
        sink.set_row_ids([1])
        sink.write_column("v", {1: 42})
    assert path.exists()


def test_excel_sink_context_exception_discards_without_final_file(tmp_path: Path) -> None:
    path = tmp_path / "discard.xlsx"
    with pytest.raises(RuntimeError, match=r"boom"):
        with ExcelSink(str(path), field_names=["v"], include_header=True) as sink:
            sink.write_row({"v": 1})
            raise RuntimeError("boom")
    assert not path.exists()


def test_excel_sink_discard_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "idem.xlsx"
    sink = ExcelSink(str(path), field_names=["v"], include_header=True)
    sink.write_row({"v": 1})
    sink.discard()
    sink.discard()
    assert not path.exists()

    col = ColumnExcelSink(str(tmp_path / "col_idem.xlsx"), field_names=["v"], include_header=True)
    col.set_row_ids([1])
    col.write_column("v", {1: 1})
    col.discard()
    col.discard()

    wb = ExcelWorkbookSink(str(tmp_path / "wb_idem.xlsx"))
    _ = wb.create_sheet_row_sink("s", field_names=["v"], include_header=True)
    wb.discard()
    wb.discard()

    stream = StreamingColumnExcelSink(str(tmp_path / "stream_idem.xlsx"), field_names=["v"], include_header=True)
    stream.set_row_ids([1])
    stream.write_column("v", {1: 1})
    stream.discard()
    stream.discard()

    csv_sink = CSVSink(str(tmp_path / "idem.csv"), field_names=["v"], include_header=True)
    csv_sink.write_row({"v": 1})
    csv_sink.discard()
    csv_sink.discard()

    col_csv = ColumnCSVSink(str(tmp_path / "col_idem.csv"), field_names=["v"], include_header=True)
    col_csv.set_row_ids([1])
    col_csv.write_column("v", {1: 1})
    col_csv.discard()
    col_csv.discard()


def test_csv_sink_discard_unlink_oserror_is_best_effort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "unlink_fail.csv"
    sink = CSVSink(str(path), field_names=["v"], include_header=True)
    sink.write_row({"v": 1})
    real_unlink = Path.unlink

    def _boom(self: Path, *args: object, **kwargs: object) -> None:
        if str(self).endswith(".csv.tmp") or ".tmp" in str(self):
            raise OSError("boom")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _boom)
    sink.discard()


def test_csv_sink_discard_when_temp_already_gone(tmp_path: Path) -> None:
    path = tmp_path / "gone.csv"
    sink = CSVSink(str(path), field_names=["v"], include_header=True)
    sink.write_row({"v": 1})
    Path(sink._temp_path).unlink()
    sink.discard()


def test_exit_sink_tolerates_missing_discard_and_close() -> None:
    from scalim.sinks._internal.base import exit_sink

    class _Bare:
        pass

    exit_sink(_Bare(), RuntimeError)
    exit_sink(_Bare(), None)


def test_column_excel_and_workbook_discard_on_exception(tmp_path: Path) -> None:
    col_path = tmp_path / "col_discard.xlsx"
    with pytest.raises(RuntimeError, match=r"boom"):
        with ColumnExcelSink(str(col_path), field_names=["v"], include_header=True) as sink:
            sink.set_row_ids([1])
            sink.write_column("v", {1: 1})
            raise RuntimeError("boom")
    assert not col_path.exists()

    wb_path = tmp_path / "wb_discard.xlsx"
    with pytest.raises(RuntimeError, match=r"boom"):
        with ExcelWorkbookSink(str(wb_path)) as wb:
            sheet = wb.create_sheet_row_sink("s", field_names=["v"], include_header=True)
            sheet.write_row({"v": 1})
            raise RuntimeError("boom")
    assert not wb_path.exists()


def test_workbook_sheet_row_sink_precheck_on(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    path = tmp_path / "wb_pre.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with ExcelWorkbookSink(str(path)) as wb:
            sheet = wb.create_sheet_row_sink(
                "s",
                field_names=["v"],
                include_header=True,
                type_precheck=SinkTypePrecheck.ON,
            )
            sheet.write_row({"v": np.datetime64("2024-01-02T03:04:05")})
    assert not path.exists()


def test_csv_and_column_csv_discard_on_exception(tmp_path: Path) -> None:
    csv_path = tmp_path / "discard.csv"
    with pytest.raises(RuntimeError, match=r"boom"):
        with CSVSink(str(csv_path), field_names=["v"], include_header=True) as sink:
            sink.write_row({"v": 1})
            raise RuntimeError("boom")
    assert not csv_path.exists()

    col_path = tmp_path / "col_discard.csv"
    with pytest.raises(RuntimeError, match=r"boom"):
        with ColumnCSVSink(str(col_path), field_names=["v"], include_header=True) as sink:
            sink.set_row_ids([1])
            sink.write_column("v", {1: 1})
            raise RuntimeError("boom")
    assert not col_path.exists()


def test_streaming_column_excel_precheck_and_discard(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    path = tmp_path / "stream.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with StreamingColumnExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
            sink.set_row_ids([1])
            sink.write_column("v", {1: np.datetime64("2024-01-02T03:04:05")})
    assert not path.exists()

    path2 = tmp_path / "stream_disc.xlsx"
    with pytest.raises(RuntimeError, match=r"boom"):
        with StreamingColumnExcelSink(str(path2), field_names=["v"], include_header=True) as sink:
            sink.set_row_ids([1])
            sink.write_column("v", {1: 1})
            raise RuntimeError("boom")
    assert not path2.exists()


def test_counting_output_row_sink_discard_delegates(tmp_path: Path) -> None:
    path = tmp_path / "count.xlsx"
    inner = ExcelSink(str(path), field_names=["v"], include_header=True)
    wrapped = _CountingOutputRowSink(inner, RowCounter())
    wrapped.write_row({"v": 1})
    wrapped.discard()
    assert not path.exists()

    class _NoDiscard:
        def write_row(self, row: object) -> None:
            _ = row

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

    wrapped2 = _CountingOutputRowSink(_NoDiscard(), RowCounter())  # type: ignore[arg-type]
    wrapped2.discard()


def test_column_excel_write_columns_and_batch_honor_precheck(tmp_path: Path) -> None:
    np = pytest.importorskip("numpy")
    bad = np.datetime64("2024-01-02T03:04:05")
    path = tmp_path / "col_batch.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with ColumnExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
            sink.set_row_ids([1])
            sink.write_columns({"v": {1: bad}})
    assert not path.exists()

    path2 = tmp_path / "col_rows.xlsx"
    with pytest.raises(TypeError, match=r"sink type precheck failed"):
        with ColumnExcelSink(str(path2), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
            sink.write_batch([{"v": bad}])
    assert not path2.exists()

    path3 = tmp_path / "col_rows_ok.xlsx"
    with ColumnExcelSink(str(path3), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
        sink.write_batch([{"v": 9}])
    assert path3.exists()


def test_run_ir_engine_failure_discards_excel_without_final_file(tmp_path: Path) -> None:
    from scalim.execution import ExecutionRequest, ExportLayout, OutputSpec, run_ir
    from scalim.execution.runtime_bindings import RuntimeBindings
    from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

    out = tmp_path / "fail.xlsx"

    def _rows():
        yield {"order_id": 1}
        raise RuntimeError("boom-mid-run")

    main_source = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    demand_ir = DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="order_id", name="Order ID", source=main_source)],
        main_source=main_source,
    )
    request = ExecutionRequest(
        export_layout=ExportLayout(field_ids=("order_id",), header_names=None),
        output=OutputSpec(format="excel", path=str(out), streaming=True, include_header=True),
        runtime_bindings=RuntimeBindings(main_source_loaders={"orders": _rows}),
    )
    with pytest.raises(RuntimeError, match=r"boom-mid-run"):
        _ = run_ir(demand_ir, request)
    assert not out.exists()


def test_tee_and_counting_discard_forwards() -> None:
    import importlib

    from scalim.sinks import BaseRowSink, BaseSink, IColumnSink
    from scalim.typedefs import RowData

    run_ir_mod = importlib.import_module("scalim.execution.run_ir")

    class _TrackRow(BaseRowSink):
        def __init__(self) -> None:
            self.discarded = False

        def write_row(self, row: object) -> None:
            _ = row

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

        def discard(self) -> None:
            self.discarded = True

    class _TrackCol(IColumnSink):
        def __init__(self) -> None:
            self.discarded = False

        def set_row_ids(self, row_ids: object) -> None:
            _ = row_ids

        def write_column(self, field_key: str, values: object) -> None:
            _ = (field_key, values)

        def write_columns(self, columns: object) -> None:
            _ = columns

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

        def discard(self) -> None:
            self.discarded = True

    class _TrackBatch(BaseSink):
        def __init__(self) -> None:
            self.discarded = False

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

        def discard(self) -> None:
            self.discarded = True

    a = _TrackRow()
    b = _TrackRow()
    run_ir_mod._TeeRowSink(a, b).discard()
    assert a.discarded and b.discarded

    c1 = _TrackCol()
    c2 = _TrackCol()
    run_ir_mod._TeeColumnSink(c1, c2).discard()
    assert c1.discarded and c2.discarded

    b1 = _TrackBatch()
    b2 = _TrackBatch()
    run_ir_mod._TeeBatchSink(b1, b2).discard()
    assert b1.discarded and b2.discarded

    tracker = run_ir_mod.InternalStatsCollector()
    inner = _TrackCol()
    run_ir_mod._CountingColumnSink(inner, tracker).discard()
    assert inner.discarded is True
    inner2 = _TrackBatch()
    run_ir_mod._CountingBatchSink(inner2, tracker).discard()
    assert inner2.discarded is True


def test_column_excel_write_columns_precheck_on_accepts_ok(tmp_path: Path) -> None:
    path = tmp_path / "cols_ok.xlsx"
    with ColumnExcelSink(str(path), field_names=["v"], include_header=True, type_precheck=SinkTypePrecheck.ON) as sink:
        sink.set_row_ids([1])
        sink.write_columns({"v": {1: 7}})
    assert path.exists()


def test_in_memory_rows_sink_discard_clears_rows() -> None:
    from scalim.sinks.rows import InMemoryRowsSink

    sink = InMemoryRowsSink(field_ids=["v"])
    sink.write_row({"v": 1})
    sink.discard()
    assert sink.to_artifact().rows == []
    sink.discard()


def test_router_row_sink_discard_is_idempotent() -> None:
    from scalim.execution.output_composition.router import FinalTargetState, RouteState, RouterRowSink
    from scalim.execution.output_composition.sinks import RowCounter
    from scalim.sinks import BaseRowSink

    class _Track(BaseRowSink):
        def __init__(self) -> None:
            self.discarded = 0

        def write_row(self, row: object) -> None:
            _ = row

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

        def discard(self) -> None:
            self.discarded += 1

    class _NoDiscard(BaseRowSink):
        def write_row(self, row: object) -> None:
            _ = row

        def write_batch(self, rows: object) -> None:
            _ = rows

        def close(self) -> None:
            return None

    inner = _Track()
    meta = _Track()
    audit = _Track()
    router = RouterRowSink(
        routes=[
            RouteState(
                target_id="t",
                sink=inner,
                predicate=None,
                is_primary=True,
                output_path=None,
                sheet_name=None,
            )
        ],
        failure_policy="all_fail",
        workbook_resources=[],
        meta_target=FinalTargetState(
            target_id="meta",
            sink=meta,
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
        audit_target=FinalTargetState(
            target_id="audit",
            sink=audit,
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
    )
    router.discard()
    router.discard()
    assert inner.discarded == 1
    assert meta.discarded == 1
    assert audit.discarded == 1

    # 无 `discard` 的路由/元信息 sink:跳过即可,不得回退到 `close()` promote.
    bare = RouterRowSink(
        routes=[
            RouteState(
                target_id="t2",
                sink=_NoDiscard(),
                predicate=None,
                is_primary=True,
                output_path=None,
                sheet_name=None,
            )
        ],
        failure_policy="all_fail",
        workbook_resources=[],
        meta_target=FinalTargetState(
            target_id="meta2",
            sink=_NoDiscard(),
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
        audit_target=FinalTargetState(
            target_id="audit2",
            sink=_NoDiscard(),
            output_counter=RowCounter(),
            output_path=None,
            sheet_name=None,
        ),
    )
    bare.discard()
