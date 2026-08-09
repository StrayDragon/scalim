"""覆盖 late-materializer 非 aligned `write_row` + `StageWriteClock` 路径(225-226)."""

from __future__ import annotations

from types import SimpleNamespace

from scalim.execution.context import BatchContext
from scalim.execution.executor.batch._internal.stage_spans import StageWriteClock, attach_write_clock
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.base._row_emission import RowEmissionCoordinator
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.write_precompute import LateFieldMaterializer
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import MainSourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr


def test_late_row_write_path_times_with_clock() -> None:
    class _PlainRowSink(object):
        def __init__(self) -> None:
            self.rows = []

        def write_row(self, row):  # type: ignore[no-untyped-def]
            self.rows.append(dict(row))

        def close(self) -> None:
            return

    plan = ExecutionPlan(field_specs={}, operators=(), target_fields=["a"])
    main = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    runtime = ExecutionRuntime(
        plan,
        HookManager(),
        ObserverManager(),
        main,
        sources={},
        runtime_bindings=RuntimeBindings(),
    )
    # LateFieldMaterializer 需要 runtime 上的 plan/deps;用最小 stub 绕开重图.
    late = LateFieldMaterializer(runtime=runtime, late_fields=[])
    times = [10.0, 11.5]
    clock = StageWriteClock(True, {"write": 0.0}, perf_counter=lambda: times.pop(0))
    attach_write_clock(runtime, clock)
    sink = _PlainRowSink()
    coordinator = RowEmissionCoordinator(
        runtime=runtime,
        sink=sink,  # type: ignore[arg-type]
        target_fields=["a"],
        retained_fields=set(),
        global_ready_fields=set(),
        allow_release=False,
        late_materializer=late,
    )
    ctx = BatchContext()
    ctx.set_field_value("a", 0, 7)
    coordinator.attach_context(ctx)
    coordinator.set_write_order([0])
    coordinator.on_field_set("a", 0)
    assert sink.rows == [{"a": 7}]
    assert clock.stage_durations["write"] == 1.5
