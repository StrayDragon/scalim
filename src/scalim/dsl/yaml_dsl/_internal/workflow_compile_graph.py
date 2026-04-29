"""`workflow` 编译: 构建 `DAG` (纯规则).

职责:
- 将 `WorkflowConfig.runs` 编译为需求节点 (`demand nodes`) + 边 (`edges`) + `slots` 映射.

边界:
- 本模块不读取 `demand YAML`, 不做 `filesystem IO` (仅解析与组装 `DAG`).
- 本模块不负责 `resources` / `outputs` / `runtime options` 等编译逻辑.
"""

from typing import Dict, List, Mapping, Optional, Tuple

from ....spec.ir._workflow import WorkflowAnyNodeIr, WorkflowEdgeIr, WorkflowNodeIr, WorkflowNodeType
from ..workflow import WorkflowConfig, resolve_workflow_demand_path

__all__ = ()


def _build_demand_nodes_and_graph(
    wf_obj: WorkflowConfig,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[
    List[WorkflowAnyNodeIr],
    List[WorkflowEdgeIr],
    Dict[str, Tuple[str, ...]],
    Dict[str, str],
    Dict[str, List[str]],
    Dict[str, int],
]:
    nodes: List[WorkflowAnyNodeIr] = []
    edges: List[WorkflowEdgeIr] = []
    slots_by_node_id: Dict[str, Tuple[str, ...]] = {}
    demand_yaml_paths_by_run_id: Dict[str, str] = {}
    direct_dependents_by_run_id: Dict[str, List[str]] = {}
    demand_node_pos_by_run_id: Dict[str, int] = {}

    for idx, run in enumerate(wf_obj.runs):
        demand_path = resolve_workflow_demand_path(
            run.demand,
            workflow_yaml_path=workflow_yaml_path,
            path_aliases=path_aliases,
            run_id=run.id,
            allowed_yaml_roots=allowed_yaml_roots,
        )
        node_id = str(run.id)
        run_deps = tuple(str(d) for d in (run.depends_on or ()))
        main_rows_from_run_id = run.main_rows_from_run_id
        if main_rows_from_run_id is not None:
            main_rows_from_run_id = str(main_rows_from_run_id or "").strip() or None
        init_vars = run.init_vars
        if init_vars is not None:
            init_vars = dict(init_vars)
        demand_yaml_paths_by_run_id[node_id] = str(demand_path)
        nodes.append(
            WorkflowNodeIr(
                node_id=node_id,
                node_type=WorkflowNodeType.DEMAND,
                decl_order=int(idx),
                deps=run_deps,
                demand_path=str(demand_path),
                init_vars=init_vars,
                main_rows_from_run_id=main_rows_from_run_id,
            )
        )
        demand_node_pos_by_run_id[node_id] = int(len(nodes) - 1)
        for dep_id in run_deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=node_id))
            direct_dependents_by_run_id.setdefault(str(dep_id), []).append(node_id)
        slots_by_node_id[node_id] = ("output_path", "outputs")

    return (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    )


def build_demand_nodes_and_graph(
    wf_obj: WorkflowConfig,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[
    List[WorkflowAnyNodeIr],
    List[WorkflowEdgeIr],
    Dict[str, Tuple[str, ...]],
    Dict[str, str],
    Dict[str, List[str]],
    Dict[str, int],
]:
    """`_build_demand_nodes_and_graph` 的跨模块入口包装.

    说明:
    - `pyright` 会将下划线前缀符号视为模块私有;该包装函数用于跨模块调用。
    """

    return _build_demand_nodes_and_graph(
        wf_obj,
        workflow_yaml_path=workflow_yaml_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )
