"""`workflow` 阶段归因辅助函数.

说明:
- `stage`/`level` 都是基于 `DAG` 拓扑的派生属性,用于调度/可视化/排障解释.
- 实现必须兼容 `Python 3.6`.
"""

from typing import Dict, Set

from ..spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowIr,
    WriteSheetNodeIr,
)


def derive_workflow_struct_levels(workflow_ir: WorkflowIr) -> Dict[str, int]:
    """推导 `workflow` `DAG` 的拓扑层级(`level`).

    `level` 定义:
    - 当 `deps` 为空, `level(node)=0`
    - 其它节点, `level(node)=max(level(dep))+1`

    备注:
    - `cycle` 本应在编译阶段被拒绝;这里仍提供 `visiting` 回退以避免派生信息导致崩溃.
    """

    node_by_id: Dict[str, WorkflowAnyNodeIr] = {}
    for node in workflow_ir.nodes:
        node_id = str(node.node_id or "").strip()
        if node_id:
            node_by_id[node_id] = node

    visiting: Set[str] = set()
    memo: Dict[str, int] = {}

    def _level(node_id: str) -> int:
        cached = memo.get(node_id)
        if cached is not None:
            return int(cached)
        if node_id in visiting:
            return 0
        visiting.add(node_id)
        node = node_by_id.get(node_id)
        deps = () if node is None else (node.deps or ())
        max_dep = -1
        for dep_id in deps:
            dep_key = str(dep_id or "").strip()
            if not dep_key or dep_key == node_id:
                continue
            max_dep = max(max_dep, _level(dep_key))
        visiting.remove(node_id)
        value = max_dep + 1 if max_dep >= 0 else 0
        memo[node_id] = int(value)
        return int(value)

    for node in workflow_ir.nodes:
        node_id = str(node.node_id or "").strip()
        if node_id:
            _ = _level(node_id)

    return memo


def derive_workflow_user_stages(workflow_ir: WorkflowIr, *, struct_levels: Dict[str, int]) -> Dict[str, int]:
    """推导用户侧 `stage` 归因.

    规则:
    - 对 `demand` 节点: `stage = level`
    - 对内部 `write` 节点: `stage` 折叠到其输入 `demand` 节点的 `stage`(更贴近用户对“阶段”的理解)

    注意:
    - 该 `stage` 主要用于解释与阶段屏障调度; `struct_levels` 仍应保留用于诊断/布局.
    """

    stages: Dict[str, int] = dict(struct_levels or {})

    for node in workflow_ir.nodes:
        node_id = str(node.node_id or "").strip()
        if not node_id:
            continue
        if isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            input_node_id = str(node.input_node_id or "").strip()
            if input_node_id:
                stages[node_id] = int(stages.get(input_node_id, struct_levels.get(input_node_id, stages.get(node_id, 0))))
    return stages


__all__ = ()
