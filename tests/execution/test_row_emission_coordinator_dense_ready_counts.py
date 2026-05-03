from typing import Any, Sequence

from scalim.execution.context import DenseBatchContext
from scalim.execution.pipeline.base._row_emission import RowEmissionCoordinator
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.plan import ExecutionPlan

from tests.fixtures.executor_operator_fixtures import _make_runtime


class _NoopRowSink(object):
    def write_row(self, _row: Any) -> None:
        return None

    def close(self) -> None:
        return None

    def write_batch(self, _rows: Sequence[Any]) -> None:
        return None


def test_row_emission_coordinator_dense_ready_counts_falls_back_for_out_of_range_row_id() -> None:
    runtime = _make_runtime(ExecutionPlan(field_specs={}), None, runtime_bindings=RuntimeBindings())
    sink = _NoopRowSink()

    coordinator = RowEmissionCoordinator(
        runtime=runtime,
        sink=sink,  # type: ignore[arg-type]
        target_fields=("a", "b"),
        retained_fields=set(),
        global_ready_fields=set(),
        allow_release=False,
    )

    ctx = DenseBatchContext(base_row_id=0, row_count=2)
    coordinator.attach_context(ctx)
    coordinator.set_write_order([0])

    # out-of-range row_id should fall back to dict-based ready_counts tracking (覆盖 on_field_set 的 idx 越界分支)
    coordinator.on_field_set("a", 999)
    assert coordinator._is_row_ready(999) is False  # noqa: SLF001  # 内部热路径行为断言
