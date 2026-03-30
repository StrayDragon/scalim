# region imports

import logging
from typing import Any, Dict, List

from ..vendor.dataclassesx import dataclass, field
from ._internal.console_report import emit_info, format_seconds

# endregion

_LOGGER = logging.getLogger(__name__)


@dataclass
class LoaderMetrics:
    """加载器性能指标"""

    name: str
    call_count: int = field(default=0, init=False)
    total_duration: float = field(default=0.0, init=False)
    durations: List[float] = field(default_factory=list, init=False)
    total_records: int = field(default=0, init=False)

    def record_call(self, duration: float, record_count: int) -> None:
        self.call_count += 1
        self.total_duration += duration
        self.durations.append(duration)
        self.total_records += record_count

    @property
    def avg_duration(self) -> float:
        if self.call_count == 0:
            return 0.0
        return self.total_duration / self.call_count

    @property
    def max_duration(self) -> float:
        if not self.durations:
            return 0.0
        return max(self.durations)

    @property
    def min_duration(self) -> float:
        if not self.durations:
            return 0.0
        return min(self.durations)


@dataclass
class MetricsCollector:
    """性能指标收集器"""

    loader_metrics: Dict[str, LoaderMetrics] = field(default_factory=dict, init=False)
    batch_durations: List[float] = field(default_factory=list, init=False)
    total_batches: int = field(default=0, init=False)
    total_records: int = field(default=0, init=False)
    high_call_count_threshold: int = 10

    def get_loader_metrics(self, loader_name: str) -> LoaderMetrics:
        if loader_name not in self.loader_metrics:
            self.loader_metrics[loader_name] = LoaderMetrics(name=loader_name)
        return self.loader_metrics[loader_name]

    def record_batch(self, duration: float, record_count: int) -> None:
        self.batch_durations.append(duration)
        self.total_batches += 1
        self.total_records += record_count

    def print_summary(self) -> None:
        avg_batch = sum(self.batch_durations) / len(self.batch_durations) if self.batch_durations else 0.0
        total_loader_records = sum(m.total_records for m in self.loader_metrics.values())
        emit_info(
            _LOGGER,
            "metrics",
            "summary",
            total_batches=int(self.total_batches),
            avg_batch_duration_s=format_seconds(avg_batch, digits=2),
            total_loader_records=int(total_loader_records),
        )

        if not self.loader_metrics:
            return

        for name in sorted(self.loader_metrics.keys()):
            metrics = self.loader_metrics[name]
            emit_info(
                _LOGGER,
                "metrics",
                "loader",
                loader=str(name),
                calls=int(metrics.call_count),
                records=int(metrics.total_records),
                total_duration_s=format_seconds(metrics.total_duration, digits=3),
                avg_time_s=format_seconds(metrics.avg_duration, digits=4),
            )

    def get_summary_dict(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "total_batches": self.total_batches,
            "total_records": self.total_records,
            "batch_durations": self.batch_durations,
            "loaders": {},
        }

        for name, metrics in self.loader_metrics.items():
            summary["loaders"][name] = {
                "call_count": metrics.call_count,
                "total_duration": metrics.total_duration,
                "avg_duration": metrics.avg_duration,
                "min_duration": metrics.min_duration,
                "max_duration": metrics.max_duration,
                "total_records": metrics.total_records,
            }

        return summary


__all__ = [
    "LoaderMetrics",
    "MetricsCollector",
]
