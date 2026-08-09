"""`StageWriteClock` 边界分支覆盖(禁用 / 乱序退出 / 零时长 write)."""

from __future__ import annotations

from types import SimpleNamespace

from scalim.events import EventType
from scalim.execution.executor.batch._internal.stage_spans import (
    StageWriteClock,
    attach_write_clock,
    get_write_clock,
    init_stage_span_tracking,
)


def test_init_stage_span_tracking_disabled() -> None:
    runtime = SimpleNamespace(instrumentation=SimpleNamespace(wants=lambda _et: False))
    wants, durations, stage_map = init_stage_span_tracking(runtime)
    assert wants is False
    assert durations == {}
    assert stage_map == {}


def test_stage_write_clock_disabled_and_mismatched_exit() -> None:
    durations = {"loader": 0.0, "compute": 0.0, "write": 0.0}
    disabled = StageWriteClock(False, durations, perf_counter=lambda: 0.0)
    disabled.enter_stage("loader")
    assert disabled.exit_stage("loader") == 0.0
    with disabled.time_write():
        pass
    assert durations["write"] == 0.0

    times = [10.0, 10.0]  # zero-duration write

    def _pc() -> float:
        return times.pop(0) if times else 10.0

    clock = StageWriteClock(True, durations, perf_counter=_pc)
    clock.enter_stage("loader")
    clock.enter_stage("compute")
    # 非栈顶退出:弹出中间 `loader`
    nested = clock.exit_stage("loader")
    assert nested == 0.0
    assert clock.exit_stage("missing") == 0.0
    with clock.time_write():
        pass  # duration <= 0 → early return
    assert durations["write"] == 0.0


def test_attach_and_get_write_clock() -> None:
    runtime = SimpleNamespace()
    attach_write_clock(runtime, None)
    assert get_write_clock(runtime) is None
    clock = StageWriteClock(True, {"write": 0.0}, perf_counter=lambda: 1.0)
    attach_write_clock(runtime, clock)
    assert get_write_clock(runtime) is clock


def test_init_stage_span_tracking_enabled_map() -> None:
    runtime = SimpleNamespace(instrumentation=SimpleNamespace(wants=lambda et: et == EventType.STAGE_SPAN))
    wants, durations, stage_map = init_stage_span_tracking(runtime)
    assert wants is True
    assert set(durations) == {"loader", "compute", "write"}
    assert "LOAD" in stage_map or any(v == "loader" for v in stage_map.values())
