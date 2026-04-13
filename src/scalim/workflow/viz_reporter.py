"""工作流可视化(`viz`)快照/报告助手(`c45 Phase 1b`)."""

import json
from pathlib import Path
from typing import Dict, Iterable

from ..ob.presets._internal import viz_config as viz_config_module
from ..ob.presets._internal.viz_config import normalize_output_dir as _normalize_viz_output_dir
from ..ob.presets.viz import VizObserverConfig, build_workflow_viz_graph_snapshot
from ..sinks._internal.base import atomic_replace_temp_path, best_effort_remove_temp_path, create_temp_path
from ..spec.ir._workflow import WorkflowIr


class WorkflowVizReporter:
    _workflow_ir: WorkflowIr
    _workflow_yaml_path: str
    _config: VizObserverConfig

    def __init__(self, workflow_ir: WorkflowIr, *, workflow_yaml_path: str, base_config: VizObserverConfig) -> None:
        self._workflow_ir = workflow_ir
        self._workflow_yaml_path = str(workflow_yaml_path)
        self._config = base_config

    def _run_dir(self, run_id: str) -> Path:
        base_dir = self._config.output_dir
        if base_dir is None:
            base_dir = viz_config_module.default_viz_dir()
        output_dir = _normalize_viz_output_dir(str(base_dir))
        return Path(output_dir) / str(run_id)

    def _snapshot_path(self, run_id: str) -> Path:
        return self._run_dir(str(run_id)) / str(self._config.snapshot_filename)

    def _events_path(self, run_id: str) -> Path:
        return self._run_dir(str(run_id)) / str(self._config.events_filename)

    def _has_child_replay(self, run_id: str) -> bool:
        snapshot_path = self._snapshot_path(str(run_id))
        events_path = self._events_path(str(run_id))
        return snapshot_path.exists() and events_path.exists()

    def write_snapshot(self, state: object, output_path: str) -> None:
        snapshot_path = Path(str(output_path))
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = create_temp_path(str(snapshot_path), ".json.tmp")
        try:
            temp_file = Path(temp_path)
            with temp_file.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, default=str)
                handle.flush()
            atomic_replace_temp_path(temp_path, str(snapshot_path))
        finally:
            best_effort_remove_temp_path(temp_path)

    def fix_child_replay_links(self, replays: Iterable[str], parent_run_id: str) -> None:
        demand_run_id_by_workflow_node_id: Dict[str, str] = {}
        for run_id in replays:
            node_id = str(run_id).strip()
            if self._has_child_replay(node_id):
                demand_run_id_by_workflow_node_id[node_id] = node_id

        snapshot = build_workflow_viz_graph_snapshot(
            self._workflow_ir,
            demand_run_id_by_workflow_node_id=demand_run_id_by_workflow_node_id,
            workflow_yaml_path=self._workflow_yaml_path,
        )
        output_path = self._snapshot_path(str(parent_run_id))
        self.write_snapshot(snapshot, str(output_path))


__all__ = ()
