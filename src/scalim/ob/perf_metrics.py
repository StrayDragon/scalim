# region imports

import json
from typing import Any, Dict, List, Optional

from ..events._events import AdaptiveSchedulerDecisionEvent
from ..vendor.dataclassesx import asdict, dataclass, field

# endregion


@dataclass
class MemorySample:
    timestamp: float
    rss_mb: float
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = asdict(self)
        result["timestamp"] = round(result["timestamp"], 3)
        result["rss_mb"] = round(result["rss_mb"], 2)
        return result


@dataclass
class CpuSample:
    timestamp: float
    percent: float
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = asdict(self)
        result["timestamp"] = round(result["timestamp"], 3)
        result["percent"] = round(result["percent"], 2)
        return result


@dataclass
class LoaderStats:
    name: str
    """加载器名称."""

    call_count: int = 0
    """调用次数(包含缓存命中)."""

    exec_count: int = 0
    """实际执行次数(不含缓存命中)."""

    cache_hit_count: int = 0
    """缓存命中次数."""

    cache_miss_count: int = 0
    """缓存未命中次数."""

    total_duration: float = 0.0
    """累计耗时(秒)."""

    total_records: int = 0
    """累计返回记录数."""

    durations: List[float] = field(default_factory=list)
    """每次调用耗时列表(秒)."""

    def record_call(self, duration: float, record_count: int, cache_status: Optional[str] = None) -> None:
        self.call_count += 1
        self.total_duration += duration
        self.total_records += record_count
        self.durations.append(duration)
        if cache_status == "hit":
            self.cache_hit_count += 1
        elif cache_status == "miss":
            self.cache_miss_count += 1
            self.exec_count += 1
        else:
            self.exec_count += 1

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

    @property
    def cache_hit_rate(self) -> float:
        denominator = self.cache_hit_count + self.cache_miss_count
        if denominator == 0:
            return 0.0
        return self.cache_hit_count / denominator

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = asdict(self)
        result.pop("durations", None)
        result["cache_hit_rate"] = round(self.cache_hit_rate, 4)
        result["total_duration"] = round(self.total_duration, 4)
        result["avg_duration"] = round(self.avg_duration, 4)
        result["min_duration"] = round(self.min_duration, 4)
        result["max_duration"] = round(self.max_duration, 4)
        return result


@dataclass
class StageMetrics:
    """跨批次汇总的各阶段实际耗时."""

    loader_duration: float = 0.0
    compute_duration: float = 0.0
    write_duration: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        result = asdict(self)
        return {
            "loader": round(result["loader_duration"], 4),
            "compute": round(result["compute_duration"], 4),
            "write": round(result["write_duration"], 4),
        }


@dataclass
class AdaptiveSchedulerMetrics:
    parallel_layers: int = 0
    """并行执行的层数."""

    serial_layers: int = 0
    """串行执行的层数."""

    serial_reasons: Dict[str, int] = field(default_factory=dict)
    """串行原因计数(`reason` -> 次数)."""

    backend_counts: Dict[str, int] = field(default_factory=dict)
    """后端选择计数(`backend` -> 次数)."""

    pool_limits: Dict[str, int] = field(default_factory=dict)
    """任务池并发上限快照(`pool` -> 上限)."""

    pool_wait_ms_total: Dict[str, float] = field(default_factory=dict)
    """任务池等待累计时间(毫秒,`pool` -> 累计等待)."""

    pool_wait_ms_max: Dict[str, float] = field(default_factory=dict)
    """任务池等待最大时间(毫秒,`pool` -> 最大等待)."""

    pool_wait_count: Dict[str, int] = field(default_factory=dict)
    """任务池等待次数(`pool` -> 次数)."""

    def record_decision(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        self._record_backend(event)
        self._record_parallelism(event)
        self._record_pool_limits(event)
        self._record_pool_wait(event)

    def _record_backend(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        backend = event.backend or ""
        if not backend:
            return
        self.backend_counts[backend] = int(self.backend_counts.get(backend, 0)) + 1

    def _record_parallelism(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        decision = event.decision or ""
        if decision == "parallel":
            self.parallel_layers += 1
            return
        self.serial_layers += 1
        reason = event.reason or "unknown"
        self.serial_reasons[reason] = int(self.serial_reasons.get(reason, 0)) + 1

    def _record_pool_limits(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        if not event.pool_limits:
            return
        for name, limit in event.pool_limits.items():
            if name and name not in self.pool_limits:
                self.pool_limits[name] = int(limit)

    def _record_pool_wait(self, event: AdaptiveSchedulerDecisionEvent) -> None:
        if event.pool_wait_ms_total:
            for name, wait_ms in event.pool_wait_ms_total.items():
                self.pool_wait_ms_total[name] = float(self.pool_wait_ms_total.get(name, 0.0)) + float(wait_ms)

        if event.pool_wait_ms_max:
            for name, wait_ms in event.pool_wait_ms_max.items():
                self.pool_wait_ms_max[name] = max(float(self.pool_wait_ms_max.get(name, 0.0)), float(wait_ms))

        if event.pool_wait_count:
            for name, count in event.pool_wait_count.items():
                self.pool_wait_count[name] = int(self.pool_wait_count.get(name, 0)) + int(count)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parallel_layers": int(self.parallel_layers),
            "serial_layers": int(self.serial_layers),
            "serial_reasons": dict(self.serial_reasons),
            "backends": dict(self.backend_counts),
            "pools": {
                "limits": dict(self.pool_limits),
                "wait_ms_total": {k: round(float(v), 3) for k, v in self.pool_wait_ms_total.items()},
                "wait_ms_max": {k: round(float(v), 3) for k, v in self.pool_wait_ms_max.items()},
                "wait_count": dict(self.pool_wait_count),
            },
        }


@dataclass
class PerformanceMetrics:
    """`PerformanceObserver` 收集的结构化性能指标.

    注意:
    - `total_rows` 统计的是输入的 `row_ids`(即 `BatchStartEvent.row_ids` 的总和),以避免逐行开销;
      它可能与 `ExecutionResult.total_rows`(写入到最终 `sink` 的行数)不同.
    """

    total_duration: float = 0.0
    """总耗时(秒)."""

    batch_count: int = 0
    """批次数."""

    total_rows: int = 0
    """输入行数(按 `row_ids` 口径统计)."""

    batch_durations: List[float] = field(default_factory=list)
    """每批耗时列表(秒)."""

    stage_metrics: StageMetrics = field(default_factory=StageMetrics)
    """各阶段耗时汇总."""

    loader_stats: Dict[str, LoaderStats] = field(default_factory=dict)
    """按加载器汇总的统计信息(`loader_name` -> `LoaderStats`)."""

    memory_samples: Optional[List[MemorySample]] = None
    """可选:内存采样列表."""

    cpu_samples: Optional[List[CpuSample]] = None
    """可选:CPU 采样列表."""

    start_memory_mb: Optional[float] = None
    """开始时内存(单位:兆字节)."""

    peak_memory_mb: Optional[float] = None
    """峰值内存(单位:兆字节)."""

    end_memory_mb: Optional[float] = None
    """结束时内存(单位:兆字节)."""

    adaptive_scheduler: Optional[AdaptiveSchedulerMetrics] = None
    """可选:自适应调度器指标."""

    @property
    def throughput(self) -> float:
        if self.total_duration <= 0:
            return 0.0
        return self.total_rows / self.total_duration

    @property
    def avg_batch_duration(self) -> float:
        if not self.batch_durations:
            return 0.0
        return sum(self.batch_durations) / len(self.batch_durations)

    @property
    def min_batch_duration(self) -> float:
        if not self.batch_durations:
            return 0.0
        return min(self.batch_durations)

    @property
    def max_batch_duration(self) -> float:
        if not self.batch_durations:
            return 0.0
        return max(self.batch_durations)

    @property
    def memory_increase_mb(self) -> Optional[float]:
        if self.start_memory_mb is None or self.end_memory_mb is None:
            return None
        return self.end_memory_mb - self.start_memory_mb

    def get_loader_stats(self, loader_name: str) -> LoaderStats:
        if loader_name not in self.loader_stats:
            self.loader_stats[loader_name] = LoaderStats(name=loader_name)
        return self.loader_stats[loader_name]

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "summary": {
                "total_duration": round(self.total_duration, 3),
                "batch_count": self.batch_count,
                "total_rows": self.total_rows,
                "throughput": round(self.throughput, 2),
            },
            "batches": {
                "count": self.batch_count,
                "avg_duration": round(self.avg_batch_duration, 4),
                "min_duration": round(self.min_batch_duration, 4),
                "max_duration": round(self.max_batch_duration, 4),
                "durations": [round(d, 4) for d in self.batch_durations],
            },
            "stages": self.stage_metrics.to_dict(),
            "loaders": {name: stats.to_dict() for name, stats in self.loader_stats.items()},
        }

        if self.memory_samples is not None:
            result["memory"] = {
                "start_mb": round(self.start_memory_mb, 2) if self.start_memory_mb else None,
                "end_mb": round(self.end_memory_mb, 2) if self.end_memory_mb else None,
                "peak_mb": round(self.peak_memory_mb, 2) if self.peak_memory_mb else None,
                "increase_mb": round(self.memory_increase_mb, 2) if self.memory_increase_mb else None,
                "samples": [s.to_dict() for s in self.memory_samples],
            }

        if self.cpu_samples is not None:
            result["cpu"] = {
                "samples": [s.to_dict() for s in self.cpu_samples],
            }

        if self.adaptive_scheduler is not None:
            result["adaptive_scheduler"] = self.adaptive_scheduler.to_dict()

        return result

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_csv_rows(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for i, duration in enumerate(self.batch_durations, 1):
            row: Dict[str, Any] = {
                "batch_num": i,
                "duration": round(duration, 4),
            }
            if self.memory_samples and i <= len(self.memory_samples):
                row["memory_mb"] = round(self.memory_samples[i - 1].rss_mb, 2)
            if self.cpu_samples and i <= len(self.cpu_samples):
                row["cpu_percent"] = round(self.cpu_samples[i - 1].percent, 2)
            rows.append(row)
        return rows


__all__ = (
    "AdaptiveSchedulerMetrics",
    "CpuSample",
    "LoaderStats",
    "MemorySample",
    "PerformanceMetrics",
    "StageMetrics",
)
