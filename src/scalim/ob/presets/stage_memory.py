# region imports

import logging
import time
import warnings
from typing import Any, Dict, List, Optional, Set

from ..._internal.loggingx import get_logger
from ...events import Event, EventType
from ...vendor.compact.importlibx import import_module
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass, field
from .._internal.console_report import emit_info
from ..observer import EventDispatchObserver
from ..report_formats import ConsoleJsonlReportFormat as _StageMemoryReportFormat
from ..structured_logging import emit_structured, is_jsonl_logging_installed

# endregion

_LOGGER = get_logger("stage_memory")

PSUTIL_NOT_INSTALLED_WARNING_PREFIX = "未安装 `psutil`"
STAGE_MEMORY_OBSERVER_DISABLED_WARNING = PSUTIL_NOT_INSTALLED_WARNING_PREFIX + ", 已禁用 `stage_memory` observer"


@dataclass
class StageMemorySample:
    batch_num: int
    stage: str
    duration_s: float
    rss_mb: Optional[float]
    delta_mb: Optional[float]
    timestamp: float = field(default_factory=time.time)


@dataclass
class StageMemoryConfig:
    enabled: bool = True
    sampling_interval: int = 1
    report_format: _StageMemoryReportFormat = _StageMemoryReportFormat.AUTO
    logger: logging.Logger = field(default=_LOGGER)

    @classmethod
    def default(cls) -> "StageMemoryConfig":
        return cls()


class StageMemoryObserver(EventDispatchObserver):
    """按 `stage` 采样进程 `RSS` 内存并输出观测日志.

    依赖:
    - 可选第三方 `psutil`(用于 `RSS`). 若缺失则 `warnings.warn` 并自动禁用该 `observer`.
    """

    config: StageMemoryConfig
    samples: List[StageMemorySample]
    event_types: Optional[Set[EventType]]

    _enabled: bool
    _process: Any
    _batch_last_rss_mb: Dict[int, Optional[float]]

    def __init__(self, config: Optional[StageMemoryConfig] = None) -> None:
        if config is None:
            config = StageMemoryConfig.default()
        self.config = config
        self.samples = []
        self.event_types = {
            EventType.PIPELINE_START,
            EventType.PIPELINE_END,
            EventType.BATCH_START,
            EventType.BATCH_END,
            EventType.STAGE_SPAN,
        }

        self._enabled = False
        self._process = None
        self._batch_last_rss_mb = {}

        self._init_psutil()

    def _init_psutil(self) -> None:
        if not self.config.enabled:
            self._enabled = False
            return

        try:
            psutil = import_module("psutil")
            self._process = psutil.Process()
            self._enabled = True
        except ImportError:
            self._enabled = False
            self._process = None
            self.event_types = set()
            warnings.warn(STAGE_MEMORY_OBSERVER_DISABLED_WARNING, stacklevel=2)

    def _should_sample(self, batch_num: int) -> bool:
        interval = int(self.config.sampling_interval)
        if interval <= 1:
            return True
        return int(batch_num) % interval == 0

    def _get_rss_mb(self) -> Optional[float]:
        if not self._enabled or self._process is None:
            return None
        try:
            rss = self._process.memory_info().rss
            return rss / 1024 / 1024
        except (OSError, AttributeError):
            return None

    def _should_use_jsonl(self) -> bool:
        fmt = self.config.report_format
        if fmt == _StageMemoryReportFormat.JSONL:
            return True
        if fmt in {_StageMemoryReportFormat.CONSOLE, _StageMemoryReportFormat.NONE}:
            return False
        return bool(is_jsonl_logging_installed())

    def _emit_sample(self, sample: StageMemorySample) -> None:
        if self.config.report_format == _StageMemoryReportFormat.NONE:
            return

        if self._should_use_jsonl():
            emit_structured(
                self.config.logger,
                level=logging.INFO,
                kind="stage_memory.sample",
                message="stage_memory.sample",
                fields={
                    "batch_num": int(sample.batch_num),
                    "stage": str(sample.stage),
                    "duration_s": float(sample.duration_s),
                    "rss_mb": float(sample.rss_mb) if sample.rss_mb is not None else None,
                    "delta_mb": float(sample.delta_mb) if sample.delta_mb is not None else None,
                },
            )
            return

        rss_text = "{:.1f}".format(sample.rss_mb) if sample.rss_mb is not None else None
        delta_text = "{:+.1f}".format(sample.delta_mb) if sample.delta_mb is not None else None
        emit_info(
            self.config.logger,
            "stage_memory",
            "sample",
            batch_num=int(sample.batch_num),
            stage=str(sample.stage),
            duration_s="{:.3f}".format(float(sample.duration_s)),
            rss_mb=rss_text,
            delta_mb=delta_text,
        )

    def on_pipeline_start(self, event: Event) -> None:
        _ = event
        if not self._enabled:
            return
        self._batch_last_rss_mb.clear()

    def on_pipeline_end(self, event: Event) -> None:
        _ = event
        if not self._enabled:
            return
        self._batch_last_rss_mb.clear()

    def on_batch_start(self, event: Event) -> None:
        payload = event.payload
        if not self._enabled:
            return
        if not self._should_sample(payload.batch_num):
            return
        self._batch_last_rss_mb[int(payload.batch_num)] = self._get_rss_mb()

    def on_batch_end(self, event: Event) -> None:
        payload = event.payload
        if not self._enabled:
            return
        if not self._should_sample(payload.batch_num):
            return
        _ = self._batch_last_rss_mb.pop(int(payload.batch_num), None)

    def on_stage_span(self, event: Event) -> None:
        payload = event.payload
        if not self._enabled:
            return
        if not self._should_sample(payload.batch_num):
            return

        batch_num = int(payload.batch_num)
        rss_mb = self._get_rss_mb()
        last_mb = self._batch_last_rss_mb.get(batch_num)

        delta_mb: Optional[float] = None
        if rss_mb is not None and last_mb is not None:
            delta_mb = float(rss_mb) - float(last_mb)

        self._batch_last_rss_mb[batch_num] = rss_mb

        sample = StageMemorySample(
            batch_num=batch_num,
            stage=str(payload.stage),
            duration_s=float(payload.duration),
            rss_mb=rss_mb,
            delta_mb=delta_mb,
        )
        self.samples.append(sample)
        self._emit_sample(sample)

    @override
    def close(self) -> None:
        self._batch_last_rss_mb.clear()


__all__ = (
    "PSUTIL_NOT_INSTALLED_WARNING_PREFIX",
    "STAGE_MEMORY_OBSERVER_DISABLED_WARNING",
    "StageMemoryConfig",
    "StageMemoryObserver",
    "StageMemorySample",
)
