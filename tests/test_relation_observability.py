from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from scalim.ob.presets.relations import (
    RelationConfig,
    RelationMetrics,
    RelationObserver,
    RelationSample,
    RelationSourceStats,
)


class TestRelationConfig:
    def test_default_values(self) -> None:
        config = RelationConfig()
        assert config.enabled is True
        assert config.sampling_rate == 0.01
        assert config.log_type_mismatch is True
        assert config.max_samples == 1000
        assert config.report_format == "console"
        assert config.output_path is None

    def test_custom_values(self) -> None:
        config = RelationConfig(
            enabled=False,
            sampling_rate=0.1,
            log_type_mismatch=False,
            max_samples=500,
            report_format="json",
            output_path="/tmp/report.json",
        )
        assert config.enabled is False
        assert config.sampling_rate == 0.1
        assert config.log_type_mismatch is False
        assert config.max_samples == 500
        assert config.report_format == "json"
        assert config.output_path == "/tmp/report.json"


class TestRelationSample:
    def test_creation(self) -> None:
        sample = RelationSample(
            row_id=1,
            fk_raw=123,
            fk_normalized=123,
            target_source="customers",
            result="hit",
        )
        assert sample.row_id == 1
        assert sample.fk_raw == 123
        assert sample.target_source == "customers"
        assert sample.result == "hit"


class TestRelationSourceStats:
    def test_default_values(self) -> None:
        stats = RelationSourceStats()
        assert stats.total_lookups == 0
        assert stats.hit_count == 0
        assert stats.miss_count == 0
        assert stats.null_key_count == 0
        assert stats.type_mismatch_count == 0

    def test_hit_rate_calculation(self) -> None:
        stats = RelationSourceStats(total_lookups=100, hit_count=75, miss_count=25)
        assert stats.hit_rate == 0.75

    def test_hit_rate_zero_lookups(self) -> None:
        stats = RelationSourceStats()
        assert stats.hit_rate == 0.0


class TestRelationMetrics:
    def test_default_values(self) -> None:
        metrics = RelationMetrics()
        assert metrics.total_lookups == 0
        assert metrics.hit_count == 0
        assert metrics.miss_count == 0
        assert metrics.null_key_count == 0
        assert metrics.type_mismatch_count == 0
        assert len(metrics.per_source_stats) == 0
        assert len(metrics.samples) == 0

    def test_hit_rate(self) -> None:
        metrics = RelationMetrics(total_lookups=200, hit_count=150, miss_count=50)
        assert metrics.hit_rate == 0.75

    def test_hit_rate_zero_lookups(self) -> None:
        metrics = RelationMetrics()
        assert metrics.hit_rate == 0.0

    def test_hit_rate_excludes_null_and_type_error(self) -> None:
        metrics = RelationMetrics(
            total_lookups=4,
            hit_count=1,
            miss_count=1,
            null_key_count=1,
            type_mismatch_count=1,
        )
        assert metrics.hit_rate == 0.5

    def test_to_dict(self) -> None:
        metrics = RelationMetrics(
            total_lookups=100,
            hit_count=80,
            miss_count=20,
            null_key_count=5,
            type_mismatch_count=2,
        )
        result = metrics.to_dict()
        assert result["summary"]["total_lookups"] == 100
        assert result["summary"]["hit_count"] == 80
        assert result["summary"]["miss_count"] == 20
        assert result["summary"]["null_key_count"] == 5
        assert result["summary"]["type_mismatch_count"] == 2
        assert result["summary"]["hit_rate"] == 0.8

    def test_to_json(self) -> None:
        metrics = RelationMetrics(total_lookups=50, hit_count=40)
        json_str = metrics.to_json()
        assert '"total_lookups": 50' in json_str
        assert '"hit_count": 40' in json_str

    def test_to_json_supports_decimal_in_samples(self) -> None:
        metrics = RelationMetrics()
        metrics.samples.append(
            RelationSample(
                row_id=1,
                fk_raw=Decimal("1.23"),
                fk_normalized=Decimal("1.23"),
                target_source="customers",
                result="hit",
            )
        )
        json_str = metrics.to_json()
        assert "1.23" in json_str

    def test_get_source_stats(self) -> None:
        metrics = RelationMetrics()
        stats = metrics.get_source_stats("customers")
        assert stats.total_lookups == 0
        assert "customers" in metrics.per_source_stats


class TestRelationObserver:
    def test_initialization(self) -> None:
        observer = RelationObserver()
        assert observer.config.enabled is True
        assert observer.metrics.total_lookups == 0

    def test_initialization_with_config(self) -> None:
        config = RelationConfig(sampling_rate=0.5)
        observer = RelationObserver(config=config)
        assert observer.config.sampling_rate == 0.5

    def test_record_lookup_hit(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)

        observer.record_lookup(
            row_id=1,
            fk_raw=123,
            fk_normalized=123,
            target_source="customers",
            result="hit",
        )

        assert observer.metrics.total_lookups == 1
        assert observer.metrics.hit_count == 1
        assert observer.metrics.miss_count == 0
        assert "customers" in observer.metrics.per_source_stats
        stats = observer.metrics.per_source_stats["customers"]
        assert stats.total_lookups == 1
        assert stats.hit_count == 1

    def test_record_lookup_miss(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)

        observer.record_lookup(
            row_id=1,
            fk_raw=456,
            fk_normalized=456,
            target_source="customers",
            result="miss",
        )

        assert observer.metrics.total_lookups == 1
        assert observer.metrics.hit_count == 0
        assert observer.metrics.miss_count == 1

    def test_record_lookup_null_key(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)

        observer.record_lookup(
            row_id=1,
            fk_raw=None,
            fk_normalized=None,
            target_source="customers",
            result="null_key",
        )

        assert observer.metrics.total_lookups == 1
        assert observer.metrics.null_key_count == 1

    def test_record_lookup_type_error(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)

        observer.record_lookup(
            row_id=1,
            fk_raw="abc",
            fk_normalized="abc",
            target_source="customers",
            result="type_error",
            fk_type="str",
            expected_type="int",
        )

        assert observer.metrics.total_lookups == 1
        assert observer.metrics.type_mismatch_count == 1

    def test_record_lookup_disabled_noop(self) -> None:
        config = RelationConfig(enabled=False, sampling_rate=1.0)
        observer = RelationObserver(config=config)

        observer.record_lookup(
            row_id=1,
            fk_raw=123,
            fk_normalized=123,
            target_source="customers",
            result="hit",
        )

        assert observer.metrics.total_lookups == 0

    def test_sampling_collects_samples(self) -> None:
        config = RelationConfig(sampling_rate=1.0, max_samples=10)
        observer = RelationObserver(config=config)

        for i in range(5):
            observer.record_lookup(
                row_id=i,
                fk_raw=i * 10,
                fk_normalized=i * 10,
                target_source="customers",
                result="hit",
            )

        assert len(observer.metrics.samples) == 5

    def test_max_samples_limit(self) -> None:
        config = RelationConfig(sampling_rate=1.0, max_samples=3)
        observer = RelationObserver(config=config)

        for i in range(10):
            observer.record_lookup(
                row_id=i,
                fk_raw=i * 10,
                fk_normalized=i * 10,
                target_source="customers",
                result="hit",
            )

        assert len(observer.metrics.samples) == 3

    def test_get_metrics(self) -> None:
        observer = RelationObserver()
        observer.record_lookup(1, 10, 10, "customers", "hit")
        metrics = observer.get_metrics()
        assert metrics.total_lookups == 1

    def test_reset(self) -> None:
        observer = RelationObserver()
        observer.record_lookup(1, 10, 10, "customers", "hit")
        observer.reset()
        assert observer.metrics.total_lookups == 0
        assert len(observer.metrics.per_source_stats) == 0
        assert len(observer.metrics.samples) == 0

    def test_on_pipeline_start_resets_metrics(self) -> None:
        from scalim.events._events import PipelineStartEvent

        observer = RelationObserver()
        observer.record_lookup(1, 10, 10, "customers", "hit")

        event = PipelineStartEvent(targets=["field1"], batch_size=100)
        observer.on_pipeline_start(event)

        assert observer.metrics.total_lookups == 0

    def test_on_pipeline_end_outputs_report(self) -> None:
        from scalim.events._events import PipelineEndEvent

        config = RelationConfig(report_format="none")
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        event = PipelineEndEvent(total_batches=10, total_duration=1.0)
        observer.on_pipeline_end(event)

    def test_print_summary(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")
        observer.record_lookup(2, 20, 20, "customers", "miss")
        observer.record_lookup(3, 30, 30, "orders", "hit")

        observer.print_summary()

    def test_print_summary_with_type_mismatch_samples(self) -> None:
        config = RelationConfig(sampling_rate=1.0)
        observer = RelationObserver(config=config)
        observer.record_lookup(
            1, "abc", "abc", "customers", "type_error", fk_type="str", expected_type="int", error_message="type mismatch"
        )

        observer.print_summary()

    def test_json_report_to_logger(self) -> None:
        config = RelationConfig(report_format="json", output_path=None)
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        observer._output_report()

    def test_json_report_to_file(self, tmp_path: "Path") -> None:
        from pathlib import Path

        output_file = tmp_path / "report.json"
        config = RelationConfig(report_format="json", output_path=str(output_file))
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        observer._output_report()

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert "total_lookups" in content

    def test_json_report_creates_parent_dirs(self, tmp_path: "Path") -> None:
        from pathlib import Path

        output_file = tmp_path / "subdir" / "report.json"
        config = RelationConfig(report_format="json", output_path=str(output_file))
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        observer._output_report()

        assert output_file.exists()

    def test_output_report_console(self) -> None:
        config = RelationConfig(report_format="console", sampling_rate=1.0)
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        observer._output_report()

    def test_json_report_write_failure(self, tmp_path: "Path") -> None:
        blocking_file = tmp_path / "blocker"
        blocking_file.write_text("blocked", encoding="utf-8")
        output_file = blocking_file / "report.json"

        config = RelationConfig(report_format="json", output_path=str(output_file))
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")

        observer._output_report()

        assert output_file.exists() is False

    def test_close_outputs_report(self) -> None:
        config = RelationConfig(report_format="none")
        observer = RelationObserver(config=config)
        observer.record_lookup(1, 10, 10, "customers", "hit")
        observer.close()
