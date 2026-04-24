import json
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scalim.dsl.yaml_dsl._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.yaml_dsl._internal.config_parsing.project_config import load_yaml_dsl_project_config
from scalim.dsl.yaml_dsl.runtime.conversion import ConfigToIRConverter
from scalim.dsl.yaml_dsl.workflow import load_workflow_config, resolve_workflow_demand_path
from scalim.ob.presets._internal.viz_config import normalize_output_dir
from scalim.ob.presets.viz.workflow import build_workflow_viz_graph_snapshot
from scalim.planning.builder import PlanBuilder
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir._workflow import (
    WorkflowArtifactsIr,
    WorkflowEdgeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
)


class InitVarMapping(Mapping[str, object]):
    """Init vars mapping that never fails on missing keys.

    Motivation:
    - Demand YAML params templates require init vars for `{$init_var: <name>}` at compile time.
    - `viz compile` is static-only; it should not require real runtime variables.
    """

    def __init__(self, base: Optional[Mapping[str, object]] = None) -> None:
        self._base = dict(base or {})

    def __getitem__(self, key: str) -> object:
        if not isinstance(key, str):
            raise KeyError(key)
        if key in self._base:
            return self._base[key]
        return "<init_var:{}>".format(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self._base)

    def __len__(self) -> int:
        return len(self._base)

    def __contains__(self, key: object) -> bool:
        # Always report init vars as available so `compile_params_template` won't raise.
        return isinstance(key, str)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def _to_posix_path(value: str) -> str:
    return str(value).replace("\\", "/")


def _relpath_posix(path: Path, *, start: Path) -> str:
    try:
        rel = path.resolve(strict=False).relative_to(start.resolve(strict=False))
        return _to_posix_path(str(rel))
    except (ValueError, OSError):
        return _to_posix_path(os.path.relpath(str(path), start=str(start)))


def _compile_demand_plan(
    yaml_path: Path,
    *,
    init_vars: Optional[Mapping[str, object]] = None,
) -> ExecutionPlan:
    loader = YamlDemandLoader()
    config = loader.load(str(yaml_path))
    demand_ir = ConfigToIRConverter(init_vars=InitVarMapping(init_vars)).convert(config)
    return PlanBuilder(demand_ir).build(targets=list(demand_ir.fields.keys()))


def compile_demand_viz(yaml_path: Path, *, output_dir: Path) -> Tuple[Path, Path]:
    """Export static viz artifacts for a single demand YAML."""
    plan = _compile_demand_plan(yaml_path, init_vars=None)

    snapshot_path = output_dir / "viz_snapshot.json"
    schedule_path = output_dir / "viz_schedule_plan.json"
    _write_json(snapshot_path, plan.to_viz_graph_snapshot())
    _write_json(schedule_path, plan.to_viz_schedule_plan())
    return snapshot_path, schedule_path


def compile_workflow_viz(workflow_yaml_path: Path, *, output_dir: Path) -> Dict[str, Path]:
    """Export a static workflow viz bundle under `<output_dir>/scalim-viz/`.

    Outputs:
    - scalim-viz/workflow/viz_snapshot.json
    - scalim-viz/<run_id>/viz_snapshot.json
    - scalim-viz/<run_id>/viz_schedule_plan.json
    - scalim-viz/bundle_manifest.json
    """

    workflow_yaml_path = workflow_yaml_path.expanduser().resolve(strict=False)
    wf = load_workflow_config(str(workflow_yaml_path))

    project_config = load_yaml_dsl_project_config(workflow_yaml_path)
    project_root = (project_config.project_root if project_config is not None else workflow_yaml_path.parent).resolve(strict=False)

    path_aliases: Dict[str, str] = {}
    if project_config is not None:
        for alias, base in (project_config.import_aliases or {}).items():
            path_aliases[str(alias)] = str(base)
    if "@" not in path_aliases:
        path_aliases["@"] = str(project_root)

    scalim_viz_dir = Path(normalize_output_dir(str(output_dir))).expanduser().resolve(strict=False)
    scalim_viz_dir.mkdir(parents=True, exist_ok=True)

    demand_run_id_by_workflow_node_id: Dict[str, str] = {}
    nodes: List[WorkflowNodeIr] = []
    edges: List[WorkflowEdgeIr] = []

    out_paths: Dict[str, Path] = {}
    for idx, run in enumerate(wf.runs):
        run_id = str(run.id or "").strip()
        if not run_id:
            continue

        demand_yaml_path = resolve_workflow_demand_path(
            str(run.demand),
            workflow_yaml_path=str(workflow_yaml_path),
            path_aliases=path_aliases,
            run_id=run_id,
            allowed_yaml_roots=[project_root],
        )

        plan = _compile_demand_plan(demand_yaml_path, init_vars=run.init_vars)
        run_dir = scalim_viz_dir / run_id
        snapshot_path = run_dir / "viz_snapshot.json"
        schedule_path = run_dir / "viz_schedule_plan.json"
        _write_json(snapshot_path, plan.to_viz_graph_snapshot())
        _write_json(schedule_path, plan.to_viz_schedule_plan())
        out_paths["run:{}:snapshot".format(run_id)] = snapshot_path
        out_paths["run:{}:schedule".format(run_id)] = schedule_path

        demand_run_id_by_workflow_node_id[run_id] = run_id

        deps = tuple(str(x) for x in (run.depends_on or ()))
        nodes.append(
            WorkflowNodeIr(
                node_id=run_id,
                node_type=WorkflowNodeType.DEMAND,
                decl_order=int(idx),
                deps=deps,
                demand_path=str(demand_yaml_path),
                init_vars=run.init_vars,
                main_rows_from_run_id=str(run.main_rows_from_run_id) if run.main_rows_from_run_id is not None else None,
            )
        )
        for dep in deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep), to_node_id=run_id))

    workflow_ir = WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=WorkflowOptionsIr(),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    workflow_snapshot = build_workflow_viz_graph_snapshot(
        workflow_ir,
        demand_run_id_by_workflow_node_id=demand_run_id_by_workflow_node_id,
        workflow_yaml_path=str(workflow_yaml_path),
    )

    workflow_dir = scalim_viz_dir / "workflow"
    workflow_snapshot_path = workflow_dir / "viz_snapshot.json"
    _write_json(workflow_snapshot_path, workflow_snapshot)
    out_paths["workflow:snapshot"] = workflow_snapshot_path

    manifest_path = scalim_viz_dir / "bundle_manifest.json"
    directory_label = _relpath_posix(scalim_viz_dir, start=project_root)
    runs = [{"id": "workflow", "path": _relpath_posix(workflow_dir, start=project_root)}]
    for node_id in sorted(demand_run_id_by_workflow_node_id.keys()):
        run_dir = scalim_viz_dir / node_id
        runs.append({"id": node_id, "path": _relpath_posix(run_dir, start=project_root)})

    _write_json(
        manifest_path,
        {
            "version": 1,
            "directoryLabel": directory_label,
            "runs": runs,
        },
    )
    out_paths["bundle:manifest"] = manifest_path
    return out_paths


__all__ = (
    "InitVarMapping",
    "compile_demand_viz",
    "compile_workflow_viz",
)
