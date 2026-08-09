from contextlib import contextmanager
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from .....events import EventType
from .....planning.operators import OperatorType
from ...runtime.runtime import ExecutionRuntime


def init_stage_span_tracking(
    runtime,  # type: ExecutionRuntime
):
    # type: (...) -> Tuple[bool, Dict[str, float], Dict[str, str]]
    wants_stage_spans = runtime.instrumentation.wants(EventType.STAGE_SPAN)
    if not wants_stage_spans:
        return False, {}, {}

    stage_durations = {"loader": 0.0, "compute": 0.0, "write": 0.0}
    stage_map = {
        OperatorType.LOAD.value: "loader",
        OperatorType.LOAD_REF.value: "loader",
        OperatorType.COMPUTE.value: "compute",
        OperatorType.WRITE_COLUMN.value: "write",
        OperatorType.WRITE_ROW.value: "write",
        OperatorType.RELEASE.value: "write",
    }
    return wants_stage_spans, stage_durations, stage_map


class StageWriteClock(object):
    """Accumulate sink write time; track nested write inside loader/compute windows.

    Callers MUST attribute outer stage wall as ``max(0, wall - exit_stage())`` so nested
    write is not double-counted into loader/compute.
    """

    def __init__(self, enabled, stage_durations, perf_counter):
        # type: (bool, Dict[str, float], Callable[[], float]) -> None
        self.enabled = bool(enabled)
        self.stage_durations = stage_durations
        self._perf_counter = perf_counter
        # (stage_name, nested_write_s_during_window)
        self._active_stages = []  # type: List[Tuple[str, float]]

    def enter_stage(self, stage):
        # type: (str) -> None
        if not self.enabled:
            return
        self._active_stages.append((str(stage), 0.0))

    def exit_stage(self, stage):
        # type: (str) -> float
        """Pop stage window and return nested write seconds attributed during it."""
        if not self.enabled:
            return 0.0
        stage_s = str(stage)
        if self._active_stages and self._active_stages[-1][0] == stage_s:
            _name, nested = self._active_stages.pop()
            return float(nested)
        for idx in range(len(self._active_stages) - 1, -1, -1):
            if self._active_stages[idx][0] == stage_s:
                _name, nested = self._active_stages.pop(idx)
                return float(nested)
        return 0.0

    @contextmanager
    def time_write(self):
        # type: () -> Iterator[None]
        if not self.enabled:
            yield
            return
        start = self._perf_counter()
        try:
            yield
        finally:
            duration = max(0.0, self._perf_counter() - start)
            if duration <= 0.0:
                return
            self.stage_durations["write"] = float(self.stage_durations.get("write", 0.0)) + duration
            if self._active_stages:
                name, nested = self._active_stages[-1]
                if name in ("loader", "compute"):
                    self._active_stages[-1] = (name, float(nested) + duration)


def attach_write_clock(runtime, clock):
    # type: (ExecutionRuntime, Optional[StageWriteClock]) -> None
    runtime.write_stage_clock = clock


def get_write_clock(runtime):
    # type: (ExecutionRuntime) -> Optional[StageWriteClock]
    clock = runtime.write_stage_clock
    if clock is None:
        return None
    return clock  # type: StageWriteClock


__all__ = (
    "StageWriteClock",
    "attach_write_clock",
    "get_write_clock",
    "init_stage_span_tracking",
)
