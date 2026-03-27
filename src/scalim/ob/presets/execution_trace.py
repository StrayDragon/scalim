# region imports
import json
import logging
import time
from collections.abc import Sized
from typing import Any, Dict, Hashable, Iterable, List, Optional, Union, cast

from ...events import (
    BatchEndEvent,
    BatchStartEvent,
    FieldSlimEvent,
    LoaderCallEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    RowReleaseEvent,
    RowWriteEvent,
)
from ...vendor.dataclassesx import asdict, dataclass, field
from ...vendor.literich import Panel, Table
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

    def on_pipeline_start(self, event: PipelineStartEvent) -> None:
        self.pipeline_start_time = time.time()
        self.target_fields = event.targets
        self.batch_size = event.batch_size

    def on_pipeline_end(self, event: PipelineEndEvent) -> None:
        _ = event
        self.pipeline_end_time = time.time()

    def on_batch_start(self, event: BatchStartEvent) -> None:
        self.current_batch = BatchTrace(
            batch_num=event.batch_num,
            row_ids=event.row_ids,
            start_time=time.time(),
        )

    def on_batch_end(self, event: BatchEndEvent) -> None:
        _ = event
        if self.current_batch:
            self.current_batch.finish()
            self.batches.append(self.current_batch)
            self.current_batch = None

    def on_loader_call(self, event: LoaderCallEvent) -> None:
        result_count = len(event.result) if isinstance(event.result, Sized) else 0
        self.total_loader_calls += 1
        if self.current_batch:
            step = LoaderCallStep(
                loader_name=event.loader_name,
                params=LoaderCallStep.serialize_params(event.params),
                result_count=result_count,
                duration=event.duration,
            )
            self.current_batch.add_step(step)

    def on_field_slim(self, event: FieldSlimEvent) -> None:
        if self.current_batch:
            step = FieldSlimStep(
                field_key=event.field_key,
                reason=event.reason,
                remaining_fields=event.remaining_fields,
            )
            self.current_batch.add_step(step)
            self.total_field_slims += 1

    def on_row_write(self, event: RowWriteEvent) -> None:
        if self.current_batch:
            step = RowWriteStep(
                row_id=event.row_id,
                batch_num=event.batch_num,
            )
            self.current_batch.add_step(step)
            self.total_row_writes += 1

    def on_row_release(self, event: RowReleaseEvent) -> None:
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
        summary_table = Table(title="Execution Trace Summary", border_style="box")
        _ = summary_table.add_column("Metric", min_width=20)
        _ = summary_table.add_column("Value", min_width=10, align="right")

        _ = summary_table.add_row("Batches", str(len(self.batches)))
        _ = summary_table.add_row("Loader Calls", str(self.total_loader_calls))
        _ = summary_table.add_row("Field Slims", str(self.total_field_slims))
        _ = summary_table.add_row("Row Writes", str(self.total_row_writes))

        _LOGGER.info("\n%s", summary_table.render())

        if not self.batches:
            return

        last_batch = self.batches[-1]
        loader_steps = [s for s in last_batch.steps if isinstance(s, LoaderCallStep)]
        slim_count = sum(1 for s in last_batch.steps if isinstance(s, FieldSlimStep))
        write_count = sum(1 for s in last_batch.steps if isinstance(s, RowWriteStep))

        content_lines = [
            "row_id: {}".format(str(last_batch.row_ids)),
        ]
        if last_batch.duration:
            content_lines.append("耗时: {:.2f}s".format(last_batch.duration))
        content_lines.append("步骤数: {}".format(len(last_batch.steps)))

        if loader_steps:
            table = Table(show_header=False, border_style="none")
            _ = table.add_column("序号", min_width=3)
            _ = table.add_column("操作", min_width=30)
            _ = table.add_column("详情", min_width=20)
            for idx, step in enumerate(loader_steps, 1):
                _ = table.add_row(
                    str(idx),
                    "[加载] {}".format(step.loader_name),
                    "返回 {} 条, {:.2f}s".format(step.result_count, step.duration),
                )
            content_lines.append("")
            content_lines.append(table.render())

        if slim_count > 0:
            content_lines.append("[瘦身] 共 {} 次字段释放".format(slim_count))
        if write_count > 0:
            content_lines.append("[写入] 共 {} 行".format(write_count))

        panel = Panel("\n".join(content_lines), title="批次 {} 详细信息".format(last_batch.batch_num), width=60)
        _LOGGER.info("\n%s", panel.render())


__all__ = [
    "ExecutionTraceObserver",
    "FieldSlimStep",
    "LoaderCallStep",
    "RowWriteStep",
]
