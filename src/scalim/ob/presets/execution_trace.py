# region imports
import json
import logging
import time
from collections.abc import Sized
from typing import Any, Dict, Hashable, Iterable, List, Optional, Union, cast

from ...events import Event
from ...vendor.dataclassesx import asdict, dataclass, field
from .._internal.console_report import emit_info, format_seconds
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


@dataclass
class LoaderCallStep:
    """加载器调用步骤元信息"""

    step_type: str = "loader_call"
    loader_name: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    result_count: int = 0
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def serialize_params(params: Dict[str, Any]) -> Dict[str, str]:
        result: Dict[str, str] = {}
        for key, pv in params.items():
            if isinstance(pv, (set, list, tuple)):
                items = list(cast("Iterable[Any]", pv))  # pragma: allow-cast iterable typed narrowing
                result[key] = str(items)
            else:
                result[key] = str(pv)
        return result


@dataclass
class FieldSlimStep:
    """字段瘦身步骤"""

    step_type: str = "field_slim"
    field_key: str = ""
    reason: str = ""
    remaining_fields: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RowWriteStep:
    """行写入步骤"""

    step_type: str = "row_write"
    row_id: Optional[Hashable] = None
    batch_num: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.row_id is not None:
            result["row_id"] = str(self.row_id)
        return result


@dataclass
class BatchTrace:
    """单个批次的执行追踪"""

    batch_num: Optional[int] = None
    row_ids: List[Hashable] = field(default_factory=list)
    steps: "List[Union[LoaderCallStep, FieldSlimStep, RowWriteStep]]" = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None

    def add_step(self, step: "Union[LoaderCallStep, FieldSlimStep, RowWriteStep]") -> None:
        self.steps.append(step)

    def finish(self) -> None:
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["row_ids"] = [str(k) for k in self.row_ids]
        return result


class ExecutionTraceObserver(EventDispatchObserver):
    """执行追踪观察者:记录详细的执行步骤"""

    def __init__(self) -> None:
        self.batches: List[BatchTrace] = []
        self.current_batch: Optional[BatchTrace] = None

        self.pipeline_start_time: Optional[float] = None
        self.pipeline_end_time: Optional[float] = None
        self.target_fields: List[str] = []
        self.batch_size: Optional[int] = None

        self.total_loader_calls: int = 0
        self.total_field_slims: int = 0
        self.total_row_writes: int = 0

    def on_pipeline_start(self, event: Event) -> None:
        payload = event.payload
        self.pipeline_start_time = time.time()
        self.target_fields = payload.targets
        self.batch_size = payload.batch_size

    def on_pipeline_end(self, event: Event) -> None:
        _ = event
        self.pipeline_end_time = time.time()

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        self.current_batch = BatchTrace(
            batch_num=payload.batch_num,
            row_ids=payload.row_ids,
            start_time=time.time(),
        )

    def on_batch_end(self, event: Event) -> None:
        _ = event
        if self.current_batch:
            self.current_batch.finish()
            self.batches.append(self.current_batch)
            self.current_batch = None

    def on_loader_call(self, event: Event) -> None:
        payload = event.payload
        result_count = len(payload.result) if isinstance(payload.result, Sized) else 0
        self.total_loader_calls += 1
        if self.current_batch:
            step = LoaderCallStep(
                loader_name=payload.loader_name,
                params=LoaderCallStep.serialize_params(payload.params),
                result_count=result_count,
                duration=payload.duration,
            )
            self.current_batch.add_step(step)

    def on_field_slim(self, event: Event) -> None:
        payload = event.payload
        if self.current_batch:
            step = FieldSlimStep(
                field_key=payload.field_key,
                reason=payload.reason,
                remaining_fields=payload.remaining_fields,
            )
            self.current_batch.add_step(step)
            self.total_field_slims += 1

    def on_row_write(self, event: Event) -> None:
        payload = event.payload
        if self.current_batch:
            step = RowWriteStep(
                row_id=payload.row_id,
                batch_num=payload.batch_num,
            )
            self.current_batch.add_step(step)
            self.total_row_writes += 1

    def on_row_release(self, event: Event) -> None:
        _ = event

    def export_to_json(self, indent: int = 2) -> str:
        data = {
            "pipeline": {
                "start_time": self.pipeline_start_time,
                "end_time": self.pipeline_end_time,
                "batch_size": self.batch_size,
                "target_fields": self.target_fields,
            },
            "stats": {
                "total_batches": len(self.batches),
                "total_loader_calls": self.total_loader_calls,
                "total_field_slims": self.total_field_slims,
                "total_row_writes": self.total_row_writes,
            },
            "batches": [batch.to_dict() for batch in self.batches],
        }
        return json.dumps(data, ensure_ascii=False, indent=indent, default=str)

    def print_summary(self) -> None:
        emit_info(
            _LOGGER,
            "execution_trace",
            "summary",
            total_batches=len(self.batches),
            total_loader_calls=int(self.total_loader_calls),
            total_field_slims=int(self.total_field_slims),
            total_row_writes=int(self.total_row_writes),
        )

        if not self.batches:
            return

        last_batch = self.batches[-1]
        loader_steps = [s for s in last_batch.steps if isinstance(s, LoaderCallStep)]
        slim_count = sum(1 for s in last_batch.steps if isinstance(s, FieldSlimStep))
        write_count = sum(1 for s in last_batch.steps if isinstance(s, RowWriteStep))
        row_ids = [str(k) for k in last_batch.row_ids]
        row_id_samples = ",".join(row_ids[:3]) if row_ids else None

        emit_info(
            _LOGGER,
            "execution_trace",
            "last_batch",
            batch_num=int(last_batch.batch_num) if last_batch.batch_num is not None else None,
            row_count=len(row_ids),
            row_id_samples=row_id_samples,
            duration_s=format_seconds(last_batch.duration, digits=2),
            steps=len(last_batch.steps),
            loader_calls=len(loader_steps),
            field_slims=int(slim_count),
            row_writes=int(write_count),
        )

        if loader_steps:
            total = len(loader_steps)
            showing = min(5, total)
            emit_info(_LOGGER, "execution_trace", "loader_call_samples", total=total, showing=int(showing))
            for idx, step in enumerate(loader_steps[:showing], 1):
                emit_info(
                    _LOGGER,
                    "execution_trace",
                    "loader_call",
                    idx=int(idx),
                    loader=str(step.loader_name),
                    records=int(step.result_count),
                    duration_s=format_seconds(float(step.duration), digits=2),
                )


__all__ = (
    "ExecutionTraceObserver",
    "FieldSlimStep",
    "LoaderCallStep",
    "RowWriteStep",
)
