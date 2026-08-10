from contextlib import contextmanager
from typing import Callable, Dict, Iterator, List, Optional, Tuple, cast

from .....events import EventType
from .....planning.operators import OperatorType
from ...runtime.runtime import ExecutionRuntime


def init_stage_span_tracking(
    runtime: ExecutionRuntime,
) -> Tuple[bool, Dict[str, float], Dict[str, str]]:
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
    """累计 `sink` `write` 耗时;跟踪 `loader`/`compute` 窗口内的嵌套 `write`.

    调用方 `MUST` 将外层 `stage` 墙钟记为 `max(0, wall - exit_stage())`,
    以免嵌套 `write` 被双重计入 `loader`/`compute`.
    """

    enabled: bool
    stage_durations: Dict[str, float]
    _perf_counter: Callable[[], float]
    _active_stages: List[Tuple[str, float]]

    def __init__(
        self,
        enabled: bool,
        stage_durations: Dict[str, float],
        perf_counter: Callable[[], float],
    ) -> None:
        self.enabled = bool(enabled)
        self.stage_durations = stage_durations
        self._perf_counter = perf_counter
        # (`stage_name`, `nested_write_s_during_window`)
        self._active_stages = []

    def enter_stage(self, stage: str) -> None:
        if not self.enabled:
            return
        self._active_stages.append((str(stage), 0.0))

    def exit_stage(self, stage: str) -> float:
        """弹出 `stage` 窗口,返回该窗口内归因的嵌套 `write` 秒数."""
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
    def time_write(self) -> Iterator[None]:
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


def attach_write_clock(runtime: ExecutionRuntime, clock: Optional[StageWriteClock]) -> None:
    runtime.write_stage_clock = clock  # pragma: allow-dynattr optional-interface: ExecutionRuntime.write_stage_clock


def get_write_clock(runtime: ExecutionRuntime) -> Optional[StageWriteClock]:
    clock = getattr(runtime, "write_stage_clock", None)  # pragma: allow-dynattr optional-interface: ExecutionRuntime.write_stage_clock
    if clock is None:
        return None
    return cast("StageWriteClock", clock)  # pragma: allow-cast optional-interface: ExecutionRuntime.write_stage_clock


__all__ = ()
