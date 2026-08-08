# pragma: allow-c901-file plan: c60
# region imports

import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..._internal.loggingx import get_logger, prefix
from ...events import Event, EventType
from ...events._events import RelationLookupEvent
from ...typedefs import RelationLookupResult, RelationReportFormat
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import asdict, dataclass, field
from .._internal.console_report import emit_info, emit_warning, format_percent
from ..observer import EventDispatchObserver
from ..structured_logging import emit_structured, is_jsonl_logging_installed
from .run_stats import warn_high_impact_observability

# endregion

_LOGGER = get_logger("relations")


@dataclass
class RelationSample:
    row_id: Any
    fk_raw: Any
    fk_normalized: Any
    target_source: str
    result: RelationLookupResult
    timestamp: float = field(default_factory=time.time)
    fk_type: Optional[str] = None
    expected_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class RelationSourceStats:
    total_lookups: int = 0
    hit_count: int = 0
    miss_count: int = 0
    null_key_count: int = 0
    type_mismatch_count: int = 0

    @property
    def hit_rate(self) -> float:
        denominator = self.hit_count + self.miss_count
        if denominator == 0:
            return 0.0
        return self.hit_count / denominator


@dataclass
class RelationMetrics:
    """关联命中统计口径."""

    total_lookups: int = 0
    hit_count: int = 0
    miss_count: int = 0
    null_key_count: int = 0
    type_mismatch_count: int = 0
    per_source_stats: Dict[str, RelationSourceStats] = field(default_factory=dict)
    samples: List[RelationSample] = field(default_factory=list)
    type_mismatch_samples: List[RelationSample] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        denominator = self.hit_count + self.miss_count
        if denominator == 0:
            return 0.0
        return self.hit_count / denominator

    def get_source_stats(self, source_id: str) -> RelationSourceStats:
        if source_id not in self.per_source_stats:
            self.per_source_stats[source_id] = RelationSourceStats()
        return self.per_source_stats[source_id]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": {
                "total_lookups": self.total_lookups,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": round(self.hit_rate, 4),
                "null_key_count": self.null_key_count,
                "type_mismatch_count": self.type_mismatch_count,
            },
            "sources": {source_id: asdict(stats) for source_id, stats in self.per_source_stats.items()},
            "samples": [asdict(s) for s in self.samples],
            "type_mismatch_samples": [asdict(s) for s in self.type_mismatch_samples],
        }

    def to_json(self, indent: int = 2) -> str:
        # 注意: `samples` 可能包含非 `JSON` 原生类型(例如 `Decimal`/`datetime`/`tuple key` 等来自用户数据).
        # 这里用 `default=str` 保证可观测性输出足够稳健.
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, default=str)


@dataclass
class RelationConfig:
    enabled: bool = True
    sampling_rate: float = 0.01
    log_type_mismatch: bool = True
    max_samples: int = 1000
    report_format: RelationReportFormat = "console"
    output_path: Optional[str] = None
    include_details: bool = False
    logger: logging.Logger = field(default=_LOGGER)

    @classmethod
    def default(cls) -> "RelationConfig":
        return cls()


class RelationObserver(EventDispatchObserver):
    config: RelationConfig
    metrics: RelationMetrics
    _reported: bool

    def __init__(
        self,
        config: Optional[RelationConfig] = None,
    ) -> None:
        if config is None:
            config = RelationConfig.default()
        self.config = config
        if self.config.enabled:
            warn_high_impact_observability("relation_lookup_diagnostics")
        self.metrics = RelationMetrics()
        self._reported = False

    def on_relation_lookup(self, event: Event) -> None:  # noqa: C901
        payload = event.payload
        if not self.config.enabled:
            return

        m = self.metrics
        m.total_lookups += 1
        source_stats = m.get_source_stats(payload.target_source)
        source_stats.total_lookups += 1

        if payload.result == "hit":
            m.hit_count += 1
            source_stats.hit_count += 1
        elif payload.result == "miss":
            m.miss_count += 1
            source_stats.miss_count += 1
        elif payload.result == "null_key":
            m.null_key_count += 1
            source_stats.null_key_count += 1
        elif payload.result == "type_error":
            m.type_mismatch_count += 1
            source_stats.type_mismatch_count += 1

        if self.config.sampling_rate < 1.0 and random.random() > self.config.sampling_rate:  # noqa: S311
            return

        sample = RelationSample(
            row_id=payload.row_id,
            fk_raw=payload.fk_raw,
            fk_normalized=payload.fk_normalized,
            target_source=payload.target_source,
            result=payload.result,
            fk_type=payload.fk_type,
            expected_type=payload.expected_type,
            error_message=payload.error_message,
        )

        if payload.result == "type_error":
            if self.config.log_type_mismatch:
                if is_jsonl_logging_installed():
                    emit_structured(
                        self.config.logger,
                        level=logging.WARNING,
                        kind="relations.type_error",
                        message="relations.type_error",
                        fields={
                            "row_id": payload.row_id,
                            "fk_raw": payload.fk_raw,
                            "target_source": str(payload.target_source),
                            "error_message": str(payload.error_message) if payload.error_message is not None else None,
                        },
                    )
                else:
                    emit_warning(
                        self.config.logger,
                        "relations",
                        "type_error",
                        row_id=payload.row_id,
                        fk_raw=payload.fk_raw,
                        target_source=payload.target_source,
                        error=payload.error_message,
                    )
            if len(m.type_mismatch_samples) < self.config.max_samples:
                m.type_mismatch_samples.append(sample)
        elif len(m.samples) < self.config.max_samples:
            m.samples.append(sample)

    def record_lookup(
        self,
        row_id: Any,
        fk_raw: Any,
        fk_normalized: Any,
        target_source: str,
        result: RelationLookupResult,
        fk_type: Optional[str] = None,
        expected_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        payload = RelationLookupEvent(
            field_key="",
            row_id=row_id,
            fk_raw=fk_raw,
            fk_normalized=fk_normalized,
            target_source=target_source,
            result=result,
            fk_type=fk_type,
            expected_type=expected_type,
            error_message=error_message,
        )
        self.on_relation_lookup(
            Event(
                event_type=EventType.RELATION_LOOKUP,
                timestamp=time.time(),
                run_id="",
                payload=payload,
                meta={},
                seq=0,
            )
        )

    def get_metrics(self) -> RelationMetrics:
        return self.metrics

    def on_pipeline_start(self, event: Event) -> None:
        _ = event
        self.reset()

    def on_pipeline_end(self, event: Event) -> None:
        _ = event
        self._output_report()
        self._reported = True

    def print_summary(self) -> None:
        m = self.metrics
        logger = self.config.logger

        if is_jsonl_logging_installed():
            emit_structured(
                logger,
                level=logging.INFO,
                kind="relations.summary",
                message="relations.summary",
                fields={
                    "total_lookups": int(m.total_lookups),
                    "hit_count": int(m.hit_count),
                    "miss_count": int(m.miss_count),
                    "null_key_count": int(m.null_key_count),
                    "type_mismatch_count": int(m.type_mismatch_count),
                    "hit_rate": float(m.hit_rate),
                },
            )
        else:
            emit_info(
                logger,
                "relations",
                "summary",
                total_lookups=int(m.total_lookups),
                hits=int(m.hit_count),
                misses=int(m.miss_count),
                null_keys=int(m.null_key_count),
                type_errors=int(m.type_mismatch_count),
                hit_rate=format_percent(m.hit_rate, digits=2),
            )

        if m.per_source_stats:
            for source_id in sorted(m.per_source_stats.keys()):
                stats = m.per_source_stats[source_id]
                if is_jsonl_logging_installed():
                    emit_structured(
                        logger,
                        level=logging.INFO,
                        kind="relations.per_source",
                        message="relations.per_source",
                        fields={
                            "target_source": str(source_id),
                            "total_lookups": int(stats.total_lookups),
                            "hit_count": int(stats.hit_count),
                            "miss_count": int(stats.miss_count),
                            "null_key_count": int(stats.null_key_count),
                            "type_mismatch_count": int(stats.type_mismatch_count),
                            "hit_rate": float(stats.hit_rate),
                        },
                    )
                else:
                    emit_info(
                        logger,
                        "relations",
                        "per_source",
                        source=str(source_id),
                        total=int(stats.total_lookups),
                        hits=int(stats.hit_count),
                        misses=int(stats.miss_count),
                        null_keys=int(stats.null_key_count),
                        type_errors=int(stats.type_mismatch_count),
                        hit_rate=format_percent(stats.hit_rate, digits=2),
                    )

        if m.type_mismatch_samples:
            showing = min(5, len(m.type_mismatch_samples))
            if is_jsonl_logging_installed():
                emit_structured(
                    logger,
                    level=logging.INFO,
                    kind="relations.type_mismatch_samples",
                    message="relations.type_mismatch_samples",
                    fields={
                        "type_mismatch_count": len(m.type_mismatch_samples),
                        "showing": int(showing),
                    },
                )
            else:
                emit_info(logger, "relations", "type_mismatch_samples", total=len(m.type_mismatch_samples), showing=int(showing))
            for sample in m.type_mismatch_samples[:showing]:
                if is_jsonl_logging_installed():
                    emit_structured(
                        logger,
                        level=logging.INFO,
                        kind="relations.type_mismatch_sample",
                        message="relations.type_mismatch_sample",
                        fields={
                            "row_id": sample.row_id,
                            "fk_raw": sample.fk_raw,
                            "fk_type": sample.fk_type,
                            "expected_type": sample.expected_type,
                            "target_source": sample.target_source,
                            "error_message": sample.error_message,
                        },
                    )
                else:
                    emit_info(
                        logger,
                        "relations",
                        "type_mismatch_sample",
                        row_id=sample.row_id,
                        fk_raw=sample.fk_raw,
                        fk_type=sample.fk_type,
                        expected_type=sample.expected_type,
                        target_source=sample.target_source,
                        error=sample.error_message,
                    )

    def _write_json_report(self) -> None:
        output_path = self.config.output_path
        if not output_path:
            self.config.logger.info("\n%s", json.dumps(self._build_report_dict(), ensure_ascii=False, indent=2, default=str))
            return

        try:
            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(json.dumps(self._build_report_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            self.config.logger.info("%s报告已写入: %s", prefix("relations"), output_path)
        except OSError as e:
            self.config.logger.warning("%s写入报告失败: %s", prefix("relations"), e)

    def _build_report_dict(self) -> Dict[str, Any]:
        return self.metrics.to_dict()

    def _output_report(self) -> None:
        fmt = self.config.report_format
        if fmt == "none":
            return
        if fmt == "console":
            self.print_summary()
        elif fmt == "json":
            self._write_json_report()

    @override
    def close(self) -> None:
        if self._reported:
            return
        self._output_report()
        self._reported = True

    def reset(self) -> None:
        self.metrics = RelationMetrics()
        self._reported = False


__all__ = (
    "RelationConfig",
    "RelationMetrics",
    "RelationObserver",
    "RelationSample",
    "RelationSourceStats",
)
