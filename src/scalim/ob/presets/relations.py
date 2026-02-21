# region imports

import json
import logging
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...events.events import RelationLookupEvent
from ...typedefs import RelationLookupResult, RelationReportFormat
from ...vendor.compact.typing_extensionsx import override
from ...vendor.literich import Table
from ..observer import EventDispatchObserver

# endregion

_LOGGER = logging.getLogger(__name__)


@dataclass
class RelationSample:
    row_id: Any
    fk_raw: Any
    fk_normalized: Any
    target_source: str
    result: RelationLookupResult
    timestamp: float = field(default_factory=time.time)
    fk_type: str | None = None
    expected_type: str | None = None
    error_message: str | None = None


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
    per_source_stats: dict[str, RelationSourceStats] = field(default_factory=dict)
    samples: list[RelationSample] = field(default_factory=list)
    type_mismatch_samples: list[RelationSample] = field(default_factory=list)

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

    def to_dict(self) -> dict[str, Any]:
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
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass
class RelationConfig:
    enabled: bool = True
    sampling_rate: float = 0.01
    log_type_mismatch: bool = True
    max_samples: int = 1000
    report_format: RelationReportFormat = "console"
    output_path: str | None = None
    include_details: bool = False
    logger: logging.Logger = field(default=_LOGGER)

    @classmethod
    def default(cls) -> "RelationConfig":
        return cls()


class RelationObserver(EventDispatchObserver):
    config: RelationConfig
    metrics: RelationMetrics

    def __init__(
        self,
        config: RelationConfig | None = None,
    ) -> None:
        if config is None:
            config = RelationConfig.default()
        self.config = config
        self.metrics = RelationMetrics()

    def on_relation_lookup(self, event: RelationLookupEvent) -> None:  # noqa: C901
        if not self.config.enabled:
            return

        m = self.metrics
        m.total_lookups += 1
        source_stats = m.get_source_stats(event.target_source)
        source_stats.total_lookups += 1

        if event.result == "hit":
            m.hit_count += 1
            source_stats.hit_count += 1
        elif event.result == "miss":
            m.miss_count += 1
            source_stats.miss_count += 1
        elif event.result == "null_key":
            m.null_key_count += 1
            source_stats.null_key_count += 1
        elif event.result == "type_error":
            m.type_mismatch_count += 1
            source_stats.type_mismatch_count += 1

        if self.config.sampling_rate < 1.0 and random.random() > self.config.sampling_rate:  # noqa: S311
            return

        sample = RelationSample(
            row_id=event.row_id,
            fk_raw=event.fk_raw,
            fk_normalized=event.fk_normalized,
            target_source=event.target_source,
            result=event.result,
            fk_type=event.fk_type,
            expected_type=event.expected_type,
            error_message=event.error_message,
        )

        if event.result == "type_error":
            if self.config.log_type_mismatch:
                self.config.logger.warning(
                    "[RelationObserver] Type mismatch: row_id=%s, fk_raw=%s, target=%s, error=%s",
                    event.row_id,
                    event.fk_raw,
                    event.target_source,
                    event.error_message,
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
        fk_type: str | None = None,
        expected_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        event = RelationLookupEvent(
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
        self.on_relation_lookup(event)

    def get_metrics(self) -> RelationMetrics:
        return self.metrics

    def on_pipeline_start(self, event: Any) -> None:
        _ = event
        self.reset()

    def on_pipeline_end(self, event: Any) -> None:
        _ = event
        self._output_report()

    def print_summary(self) -> None:
        m = self.metrics

        summary_table = Table(title="Relation Summary", border_style="box")
        _ = summary_table.add_column("Metric", min_width=20)
        _ = summary_table.add_column("Value", min_width=15, align="right")

        _ = summary_table.add_row("Total Lookups", str(m.total_lookups))
        _ = summary_table.add_row("Hits", str(m.hit_count))
        _ = summary_table.add_row("Misses", str(m.miss_count))
        _ = summary_table.add_row("Hit Rate", f"{m.hit_rate:.2%}")
        _ = summary_table.add_row("Null Keys", str(m.null_key_count))
        _ = summary_table.add_row("Type Errors", str(m.type_mismatch_count))

        output_lines = ["\n" + summary_table.render()]

        if m.per_source_stats:
            source_table = Table(title="Per Source", border_style="box")
            _ = source_table.add_column("Source", min_width=20)
            _ = source_table.add_column("Total", min_width=6, align="right")
            _ = source_table.add_column("Hits", min_width=6, align="right")
            _ = source_table.add_column("Misses", min_width=6, align="right")
            _ = source_table.add_column("Hit Rate", min_width=10, align="right")

            for source_id, stats in m.per_source_stats.items():
                _ = source_table.add_row(
                    source_id,
                    str(stats.total_lookups),
                    str(stats.hit_count),
                    str(stats.miss_count),
                    f"{stats.hit_rate:.2%}",
                )
            output_lines.append(source_table.render())

        if m.type_mismatch_samples:
            output_lines.append(f"\nType Mismatch Samples (first {min(5, len(m.type_mismatch_samples))}):")
            for sample in m.type_mismatch_samples[:5]:
                output_lines.append(
                    "  - row_id={}, fk_raw={} ({}), target={}, error={}".format(
                        sample.row_id,
                        sample.fk_raw,
                        sample.fk_type or "unknown",
                        sample.target_source,
                        sample.error_message or "type mismatch",
                    )
                )

        self.config.logger.info("\n".join(output_lines))

    def _write_json_report(self) -> None:
        output_path = self.config.output_path
        if not output_path:
            self.config.logger.info("\n%s", json.dumps(self._build_report_dict(), ensure_ascii=False, indent=2))
            return

        try:
            path = Path(output_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            _ = path.write_text(json.dumps(self._build_report_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            self.config.logger.info("[RelationObserver] Report written to %s", output_path)
        except OSError as e:
            self.config.logger.warning("[RelationObserver] Failed to write report: %s", e)

    def _build_report_dict(self) -> dict[str, Any]:
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
        self._output_report()

    def reset(self) -> None:
        self.metrics = RelationMetrics()


__all__ = [
    "RelationConfig",
    "RelationMetrics",
    "RelationObserver",
    "RelationSample",
    "RelationSourceStats",
]
