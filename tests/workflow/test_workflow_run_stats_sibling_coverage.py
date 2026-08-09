"""覆盖 `workflow` teardown 旁路写 `run_stats` sibling 的观察者聚合分支."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scalim.ob.presets.run_stats import SCHEMA_RUN_STATS, WorkflowStatsAccumulator, resolve_viz_run_dir
from scalim.ob.presets.viz import VizObserver, VizObserverConfig
from scalim.workflow import execute as workflow_execute_mod
from tests.ob.test_run_stats import _drive_pipeline


def test_auto_write_workflow_run_stats_siblings_aggregates_demand_components(tmp_path: Path) -> None:
    run_root = tmp_path / "viz"
    run_root.mkdir()
    accum = WorkflowStatsAccumulator(sample_rss=False)
    _drive_pipeline(accum, loaders=["facts"])
    viz = VizObserver(
        config=VizObserverConfig(output_dir=str(run_root), run_id="wf_sib", append=False),
        snapshot={"nodes": [], "edges": [], "meta": {"schema_version": "vizgraph/v1"}},
    )
    viz.run_id = "wf_sib"
    viz._apply_run_output_dir()  # noqa: SLF001
    viz._write_snapshot_if_needed()  # noqa: SLF001

    demand_viz = VizObserver(
        config=VizObserverConfig(output_dir=str(tmp_path / "demand-viz"), run_id="d1", append=False),
        snapshot={"nodes": [], "edges": [], "meta": {"schema_version": "vizgraph/v1"}},
    )
    demand_viz.run_id = "d1"
    demand_viz._apply_run_output_dir()  # noqa: SLF001
    demand_viz._write_snapshot_if_needed()  # noqa: SLF001

    request = SimpleNamespace(
        components=[accum],
        observability=SimpleNamespace(viz_config=demand_viz.config),
    )
    # viz_config 存在但 resolve 为空 → 714->701 假分支
    request_empty_viz = SimpleNamespace(
        components=[],
        observability=SimpleNamespace(viz_config=SimpleNamespace(resolve_output_paths=lambda: (None, None, None), output_dir=None)),
    )
    prepared = SimpleNamespace(
        workflow_observer_manager=None,
        workflow_components=(),
        workflow_viz_observer=viz,
        captured_demand_viz_observer_by_node_id={"n1": demand_viz},
        captured_demand_request_by_node_id={"n1": request, "n2": request_empty_viz},
        workflow_exec_id="wf_exec",
    )
    workflow_execute_mod._auto_write_workflow_run_stats_siblings(prepared)  # noqa: SLF001

    wf_dir = resolve_viz_run_dir(viz)
    assert wf_dir is not None
    assert (Path(wf_dir) / "run_stats.json").is_file()
    demand_stats = list((tmp_path / "demand-viz").rglob("run_stats.json"))
    assert demand_stats
    assert SCHEMA_RUN_STATS in demand_stats[0].read_text(encoding="utf-8")
