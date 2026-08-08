import hashlib
import warnings
from pathlib import Path

import pytest

from scalim.events._events import (
    BatchEndEvent,
    BatchStartEvent,
    LoaderCallEvent,
    OutputTargetEndEvent,
    PipelineEndEvent,
    PipelineStartEvent,
    StageSpanEvent,
)
from scalim.ob.presets.profiles import (
    PROFILE_BASELINE,
    PROFILE_BENCH,
    PROFILE_DEBUG,
    build_observability_profile,
)
from scalim.ob.presets.run_stats import (
    SCHEMA_RUN_STATS,
    WorkflowStatsAccumulator,
    warn_high_impact_observability,
    write_run_stats_sibling,
)
from tests.support.event_envelope import event_envelope


def _drive_pipeline(obs, *, loaders, rows=10, batches=2):
    obs.on_pipeline_start(event_envelope(PipelineStartEvent(batch_size=5, targets=["t"])))
    for b in range(1, batches + 1):
        row_ids = list(range((b - 1) * 5, b * 5))
        obs.on_batch_start(event_envelope(BatchStartEvent(batch_num=b, row_ids=row_ids)))
        obs.on_stage_span(event_envelope(StageSpanEvent(batch_num=b, stage="loader", duration=0.01)))
        obs.on_stage_span(event_envelope(StageSpanEvent(batch_num=b, stage="compute", duration=0.02)))
        for name in loaders:
            obs.on_loader_call(
                event_envelope(
                    LoaderCallEvent(
                        loader_name=name,
                        params={},
                        duration=0.001,
                        result=[{"id": 1}] * rows,
                        cache_status="miss",
                        batch_num=b,
                    )
                )
            )
        obs.on_output_target_end(
            event_envelope(
                OutputTargetEndEvent(
                    target_id="out",
                    row_count=len(row_ids),
                    duration=0.001,
                    output_path="/tmp/x.csv",
                    sheet_name=None,
                    error_count=0,
                    disabled=False,
                )
            )
        )
        obs.on_batch_end(event_envelope(BatchEndEvent(batch_num=b, duration=0.05)))
    obs.on_pipeline_end(event_envelope(PipelineEndEvent(total_batches=batches, total_duration=0.1)))


def test_accumulator_nodes_survive_second_pipeline():
    accum = WorkflowStatsAccumulator(sample_rss=False)
    _drive_pipeline(accum, loaders=["facts", "dims"])
    _drive_pipeline(accum, loaders=["detail_rows"])
    stats = accum.build_run_stats(meta={"profile": "bench"})
    assert stats["schema"] == SCHEMA_RUN_STATS
    assert stats["pipeline"]["node_count"] == 2
    assert len(stats["nodes"]) == 2
    assert any(l["name"] == "facts" for l in stats["nodes"][0]["loaders"])
    assert any(l["name"] == "detail_rows" for l in stats["nodes"][1]["loaders"])
    assert any(l["name"] == "facts" for l in stats["loaders"])


def test_baseline_profile_empty_components():
    built = build_observability_profile(PROFILE_BASELINE)
    assert built["components"] == []
    assert built["name"] == PROFILE_BASELINE


def test_bench_profile_has_accumulator_without_relation():
    built = build_observability_profile(PROFILE_BENCH, include_memory=False)
    assert any(isinstance(c, WorkflowStatsAccumulator) for c in built["components"])
    assert built["handles"]["relation"] is None
    types = {type(c).__name__ for c in built["components"]}
    assert "RelationObserver" not in types


def test_debug_profile_emits_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        build_observability_profile(PROFILE_DEBUG, include_memory=False, viz_output_dir=None)
    messages = " ".join(str(w.message) for w in caught)
    assert "high-impact" in messages
    assert "bench" in messages


def test_warn_helper_mentions_bench():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warn_high_impact_observability("relation_lookup_diagnostics")
    assert caught
    assert "bench" in str(caught[0].message)


def test_write_run_stats_sibling_not_embedded(tmp_path: Path):
    run_dir = tmp_path / "scalim-viz" / "run_x"
    run_dir.mkdir(parents=True)
    (run_dir / "viz_snapshot.json").write_text('{"meta":{"schema_version":"vizgraph/v1"}}', encoding="utf-8")
    accum = WorkflowStatsAccumulator()
    _drive_pipeline(accum, loaders=["facts"])
    payload = accum.build_run_stats()
    out = write_run_stats_sibling(str(run_dir), payload)
    assert Path(out).name == "run_stats.json"
    assert Path(out).is_file()
    snap_text = (run_dir / "viz_snapshot.json").read_text(encoding="utf-8")
    assert "scalim_run_stats" not in snap_text
    assert SCHEMA_RUN_STATS in Path(out).read_text(encoding="utf-8")


def test_bench_does_not_mutate_synthetic_csv_bytes(tmp_path: Path):
    """Sanity: collecting run_stats is side-effect free w.r.t. a CSV artifact."""
    csv_path = tmp_path / "out.csv"
    content = "a,b\n1,2\n3,4\n"
    csv_path.write_text(content, encoding="utf-8")
    before = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    accum = WorkflowStatsAccumulator()
    _drive_pipeline(accum, loaders=["facts"])
    _ = accum.build_run_stats()
    after = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert before == after


def test_accumulator_event_types_are_lite_only():
    from scalim.events import EventType

    forbidden = {
        EventType.ROW_WRITE,
        EventType.FIELD_COMPUTE,
        EventType.RELATION_LOOKUP,
    }
    assert WorkflowStatsAccumulator.event_types.isdisjoint(forbidden)


def test_notes_document_write_and_shared_reset():
    accum = WorkflowStatsAccumulator()
    _drive_pipeline(accum, loaders=["facts"])
    notes = accum.build_run_stats()["notes"]
    assert notes["write_stage_attribution"] == "sink_path_timed"
    assert notes["sink_close_bucket"] == "write"
    assert "nodes" in notes["shared_observer_reset"]


def test_memory_without_psutil_fails(monkeypatch):
    def fail_import(name):
        if name == "psutil":
            raise ImportError("missing")
        raise AssertionError("unexpected import: {}".format(name))

    monkeypatch.setattr("scalim.vendor.compact.importlibx.import_module", fail_import)
    with pytest.raises(RuntimeError, match="psutil"):
        from scalim.ob.presets.run_stats import require_psutil_for_memory

        require_psutil_for_memory("bench.include_memory")


def test_bench_include_memory_requires_psutil(monkeypatch):
    def boom(reason):
        raise RuntimeError("memory sampling requested ({})".format(reason))

    monkeypatch.setattr(
        "scalim.ob.presets.profiles.require_psutil_for_memory",
        boom,
    )
    with pytest.raises(RuntimeError, match="memory sampling"):
        build_observability_profile(PROFILE_BENCH, include_memory=True)


def test_programmatic_relation_warns():
    from scalim.ob.presets.relations import RelationConfig, RelationObserver

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        RelationObserver(config=RelationConfig(enabled=True, report_format="none"))
    assert any("relation_lookup" in str(w.message) and "bench" in str(w.message) for w in caught)


def test_programmatic_field_compute_top_n_warns():
    from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        PerformanceObserver(config=PerformanceConfig(include_field_compute_top_n=5, report_format="none"))
    assert any("field_compute" in str(w.message) and "bench" in str(w.message) for w in caught)


def test_viz_trace_and_full_payload_warn():
    from scalim.ob.presets.viz import VizObserverConfig

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        VizObserverConfig(trace_enabled=True, payload_policy="summary")
        VizObserverConfig(trace_enabled=False, payload_policy="full")
    kinds = " ".join(str(w.message) for w in caught)
    assert "viz_trace" in kinds
    assert "viz_payload_policy_full" in kinds
    assert "bench" in kinds
