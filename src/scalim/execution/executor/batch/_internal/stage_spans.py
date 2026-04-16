from typing import Dict, Tuple

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


__all__ = ()
