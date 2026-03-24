"""`workflow` 编译阶段实现(内部模块).

说明:
- 承载 `workflow` `config` -> `workflow IR` 的编译逻辑
- 运行时需兼容 `Python 3.6`
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from ....spec.ir.workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowArtifactsIr,
    WorkflowCachePoolBudgetIr,
    WorkflowCachePoolIr,
    WorkflowCachePoolPinIr,
    WorkflowCtxOptionsIr,
    WorkflowEdgeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WorkflowResourceIr,
    WriteSheetNodeIr,
)
from ..config_parsing.loader import YamlDemandLoader
from ..workflow import (
    WorkflowConfigError,
    WorkflowWriteTo,
    WorkflowWriteToCsvAppend,
    WorkflowWriteToSheetbookAppend,
    WorkflowWriteToSheetbookSheet,
    WorkflowWriteToWorkbookAppend,
    WorkflowWriteToWorkbookSheet,
    resolve_workflow_demand_path,
)


def compile_workflow_ir(  # noqa: C901, PLR0912, PLR0915
    wf: object,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    template_vars: Optional[Mapping[str, object]] = None,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
) -> WorkflowIr:
    wf_obj = cast("Any", wf)

    nodes: List[WorkflowAnyNodeIr] = []
    edges: List[WorkflowEdgeIr] = []
    slots_by_node_id: Dict[str, Tuple[str, ...]] = {}

    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    base_dir = wf_path.parent

    resources: List[WorkflowResourceIr] = []
    raw_resources = getattr(wf_obj, "resources", None)
    if raw_resources is not None:
        for workbook_id, wb in getattr(raw_resources, "workbooks", {}).items():
            raw_path = str(getattr(wb, "path", "") or "").strip()
            resolved = (
                (base_dir / raw_path).resolve(strict=False)
                if raw_path and not Path(raw_path).is_absolute()
                else Path(raw_path).resolve(strict=False)
            )
            resources.append(
                WorkflowResourceIr(
                    resource_id=str(workbook_id),
                    resource_type="workbook",
                    path=str(resolved),
                    options=None,
                )
            )
        for csv_id, csv_cfg in getattr(raw_resources, "csvs", {}).items():
            raw_path = str(getattr(csv_cfg, "path", "") or "").strip()
            resolved = (
                (base_dir / raw_path).resolve(strict=False)
                if raw_path and not Path(raw_path).is_absolute()
                else Path(raw_path).resolve(strict=False)
            )
            resources.append(
                WorkflowResourceIr(
                    resource_id=str(csv_id),
                    resource_type="csv",
                    path=str(resolved),
                    options=None,
                )
            )
        for sheetbook_id, sb_cfg in getattr(raw_resources, "sheetbooks", {}).items():
            budget = getattr(sb_cfg, "budget", None)
            max_sheets = int(getattr(budget, "max_sheets", 0) or 0) if budget is not None else 0
            max_total_cells = int(getattr(budget, "max_total_cells", 0) or 0) if budget is not None else 0

            export_cfg = getattr(sb_cfg, "export_xlsx", None)
            raw_path = str(getattr(export_cfg, "path", "") or "").strip() if export_cfg is not None else ""
            resolved = Path()
            if raw_path:
                resolved = (
                    (base_dir / raw_path).resolve(strict=False)
                    if raw_path and not Path(raw_path).is_absolute()
                    else Path(raw_path).resolve(strict=False)
                )
            resource_options: Dict[str, object] = {
                "budget": {"max_sheets": int(max_sheets), "max_total_cells": int(max_total_cells)},
            }
            if export_cfg is not None and raw_path:
                resource_options["export_xlsx"] = {"write_lock": bool(getattr(export_cfg, "write_lock", False))}

            resources.append(
                WorkflowResourceIr(
                    resource_id=str(sheetbook_id),
                    resource_type="sheetbook",
                    path=str(resolved) if raw_path else "",
                    options=resource_options,
                )
            )

    reserved_xlsx_paths: Set[str] = set()
    for res in resources:
        if str(res.resource_type) in {"workbook", "sheetbook"}:
            res_path = str(res.path or "").strip()
            if not res_path:
                continue
            reserved_xlsx_paths.add(str(Path(res_path).expanduser().resolve(strict=False)))

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
        run_deps = tuple(str(d) for d in (getattr(run, "depends_on", ()) or ()))
        init_vars = cast("Optional[Dict[str, object]]", getattr(run, "init_vars", None))
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
            )
        )
        demand_node_pos_by_run_id[node_id] = int(len(nodes) - 1)
        for dep_id in run_deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=node_id))
            direct_dependents_by_run_id.setdefault(str(dep_id), []).append(node_id)
        slots_by_node_id[node_id] = ("output_path", "outputs")

    loader = YamlDemandLoader()
    demand_cfg_by_run_id: Dict[str, object] = {}
    workbook_writers_by_abs_path: Dict[str, Set[str]] = {}
    for node_id, yaml_path in demand_yaml_paths_by_run_id.items():
        try:
            cfg = loader.load(str(yaml_path), template_vars=template_vars, allowed_yaml_roots=allowed_yaml_roots)
        except Exception as exc:
            msg = "Failed to load demand YAML for workflow collision precheck: run_id={!r}, demand_path={!r}: {}".format(
                str(node_id),
                str(yaml_path),
                exc,
            )
            raise WorkflowConfigError(msg, path="workflow.runs[*].demand") from exc

        demand_cfg_by_run_id[str(node_id)] = cfg

        raw_paths: Set[str] = set()
        for out_cfg in getattr(cfg, "outputs", ()) or ():
            container = getattr(out_cfg, "container", None)
            if container is None:
                continue  # pragma: no cover
            if str(getattr(container, "type", "") or "").lower() != "workbook":
                continue
            raw = getattr(container, "path", None)
            if isinstance(raw, dict):
                continue
            p = str(raw or "").strip()
            if p:
                raw_paths.add(p)

        default_workbook_path = None
        for out_cfg in getattr(cfg, "outputs", ()) or ():
            container = getattr(out_cfg, "container", None)
            if container is None:
                continue  # pragma: no cover
            if str(getattr(container, "type", "") or "").lower() != "workbook":
                continue
            raw = getattr(container, "path", None)
            if isinstance(raw, dict):
                continue
            p = str(raw or "").strip()
            if p:
                default_workbook_path = p
                break

        for extra in (getattr(cfg, "meta", None), getattr(cfg, "audit", None)):
            if extra is None:
                continue
            p = str(getattr(extra, "path", "") or "").strip()
            if p:
                raw_paths.add(p)
            elif default_workbook_path:
                raw_paths.add(str(default_workbook_path))

        resolved_paths: Set[str] = set()
        for raw_path in raw_paths:
            resolved_paths.add(str(Path(str(raw_path)).expanduser().resolve(strict=False)))

        for abs_path in sorted(resolved_paths):
            if abs_path in reserved_xlsx_paths:
                msg = (
                    "Excel output path is reserved by workflow shared resources (use resources + write nodes): "
                    + "run_id={!r}, path={!r}".format(str(node_id), str(abs_path))
                )
                raise WorkflowConfigError(msg, path="workflow.runs[*].demand")
            workbook_writers_by_abs_path.setdefault(abs_path, set()).add(str(node_id))

    collisions = sorted((path, sorted(node_ids)) for path, node_ids in workbook_writers_by_abs_path.items() if len(node_ids) > 1)
    if collisions:
        path, node_ids = collisions[0]
        msg = "Excel output path collision across workflow nodes: path={!r}, nodes={}".format(str(path), ",".join(node_ids))
        raise WorkflowConfigError(msg, path="workflow.runs[*].demand")

    last_write_node_id_by_resource: Dict[Tuple[str, str], str] = {}
    sheetbook_write_node_ids_by_run_id: Dict[str, List[str]] = {}
    for run_idx, run in enumerate(wf_obj.runs):
        writes = cast("Tuple[WorkflowWriteTo, ...]", tuple(getattr(run, "writes", ()) or ()))
        if not writes:
            continue

        output_type_by_id: Dict[str, str] = {}
        cfg = demand_cfg_by_run_id.get(str(run.id))
        if cfg is not None:
            for out_cfg in getattr(cfg, "outputs", ()) or ():
                out_id = str(getattr(out_cfg, "name", "") or "").strip()
                container = getattr(out_cfg, "container", None)
                out_type = str(getattr(container, "type", "") or "")
                if out_id:
                    output_type_by_id[out_id] = out_type

        def _intent_kind(value: object) -> str:
            if isinstance(value, WorkflowWriteToWorkbookSheet):
                return "workbook_sheet"
            if isinstance(value, WorkflowWriteToWorkbookAppend):
                return "workbook_append"
            if isinstance(value, WorkflowWriteToCsvAppend):
                return "csv_append"
            if isinstance(value, WorkflowWriteToSheetbookSheet):
                return "sheetbook_sheet"
            if isinstance(value, WorkflowWriteToSheetbookAppend):
                return "sheetbook_append"
            return "unknown"  # pragma: no cover

        for write_idx, intent in enumerate(writes):
            kind = _intent_kind(intent)
            output_id = str(getattr(intent, "output", "") or "").strip()
            resource_type = ""
            resource_id = ""

            if isinstance(intent, (WorkflowWriteToWorkbookSheet, WorkflowWriteToWorkbookAppend)):
                resource_type = "workbook"
                resource_id = str(getattr(intent, "workbook", "") or "")
            elif isinstance(intent, WorkflowWriteToCsvAppend):
                resource_type = "csv"
                resource_id = str(getattr(intent, "csv", "") or "")
            elif isinstance(intent, (WorkflowWriteToSheetbookSheet, WorkflowWriteToSheetbookAppend)):
                resource_type = "sheetbook"
                resource_id = str(getattr(intent, "sheetbook", "") or "")

            if output_id not in output_type_by_id:
                msg = (
                    "Unknown demand output id referenced by workflow writes: "
                    "run_id={!r}, intent_kind={!r}, resource_id={!r}, output_id={!r}"
                ).format(str(run.id), str(kind), str(resource_id), str(output_id))
                raise WorkflowConfigError(
                    msg,
                    path="workflow.runs.{}.writes.{}.{}.output".format(int(run_idx), int(write_idx), str(kind)),
                )
            if str(output_type_by_id.get(output_id, "")).lower() != "csv":
                msg = (
                    "workflow writes currently only supports CSV outputs: run_id={!r}, intent_kind={!r}, resource_id={!r}, output_id={!r}"
                ).format(str(run.id), str(kind), str(resource_id), str(output_id))
                raise WorkflowConfigError(
                    msg,
                    path="workflow.runs.{}.writes.{}.{}.output".format(int(run_idx), int(write_idx), str(kind)),
                )

            node_id = "{}write.{}.{}".format("__wf__", str(run.id), int(write_idx))
            decl_order = len(nodes)
            write_deps: List[str] = [str(run.id)]

            node: WorkflowAnyNodeIr
            if isinstance(intent, WorkflowWriteToWorkbookSheet):
                sheet_name = str(intent.sheet)
                on_conflict = str(intent.on_conflict or "error")
                node = WriteSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.WRITE_SHEET,
                    decl_order=int(decl_order),
                    deps=(),
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    sheet=sheet_name,
                    input_node_id=str(run.id),
                    input_output_id=str(output_id),
                    on_conflict=on_conflict,
                )
            elif isinstance(intent, WorkflowWriteToWorkbookAppend):
                node = AppendSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.APPEND_SHEET,
                    decl_order=int(decl_order),
                    deps=(),
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    sheet=str(intent.sheet),
                    input_node_id=str(run.id),
                    input_output_id=str(output_id),
                    align_by=str(intent.align_by or "field_id"),
                    header_policy=str(intent.header_policy or "once"),
                    on_mismatch=str(intent.on_mismatch or "error"),
                )
            elif isinstance(intent, WorkflowWriteToCsvAppend):
                node = AppendSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.APPEND_SHEET,
                    decl_order=int(decl_order),
                    deps=(),
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    sheet=None,
                    input_node_id=str(run.id),
                    input_output_id=str(output_id),
                    align_by="header",
                    header_policy=str(intent.header_policy or "once"),
                    on_mismatch=str(intent.on_mismatch or "error"),
                )
            elif isinstance(intent, WorkflowWriteToSheetbookSheet):
                sheet_name = str(intent.sheet)
                on_conflict = str(intent.on_conflict or "error")
                node = WriteSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.WRITE_SHEET,
                    decl_order=int(decl_order),
                    deps=(),
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    sheet=sheet_name,
                    input_node_id=str(run.id),
                    input_output_id=str(output_id),
                    on_conflict=on_conflict,
                )
                sheetbook_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))
            elif isinstance(intent, WorkflowWriteToSheetbookAppend):
                node = AppendSheetNodeIr(
                    node_id=str(node_id),
                    node_type=WorkflowNodeType.APPEND_SHEET,
                    decl_order=int(decl_order),
                    deps=(),
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    sheet=str(intent.sheet),
                    input_node_id=str(run.id),
                    input_output_id=str(output_id),
                    align_by=str(intent.align_by or "field_id"),
                    header_policy=str(intent.header_policy or "once"),
                    on_mismatch=str(intent.on_mismatch or "error"),
                )
                sheetbook_write_node_ids_by_run_id.setdefault(str(run.id), []).append(str(node_id))
            else:  # pragma: no cover
                continue  # pragma: no cover

            resource_key = (resource_type, str(resource_id))
            prev_write_id = last_write_node_id_by_resource.get(resource_key)
            if prev_write_id is not None:
                write_deps.append(str(prev_write_id))
            last_write_node_id_by_resource[resource_key] = str(node_id)

            node = replace(node, deps=tuple(write_deps))
            nodes.append(node)
            for dep_id in write_deps:
                edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=str(node_id)))

    # `sheetbook` 可作为输入: 为直接依赖该生产者的节点增加对其写入节点的依赖,确保读取时已写入.
    for producer_node_id, write_node_ids in sheetbook_write_node_ids_by_run_id.items():
        for consumer_node_id in direct_dependents_by_run_id.get(str(producer_node_id), []):
            pos = demand_node_pos_by_run_id.get(str(consumer_node_id))
            if pos is None:
                continue  # pragma: no cover
            consumer = nodes[int(pos)]
            if not isinstance(consumer, WorkflowNodeIr):
                continue  # pragma: no cover
            deps: List[str] = list(consumer.deps or ())
            for write_node_id in write_node_ids:
                if str(write_node_id) not in deps:
                    deps.append(str(write_node_id))
                    edges.append(WorkflowEdgeIr(from_node_id=str(write_node_id), to_node_id=str(consumer_node_id)))
            if deps != list(consumer.deps or ()):
                nodes[int(pos)] = replace(consumer, deps=tuple(deps))

    cache_pool = None
    raw_cache_pool = getattr(wf_obj.options, "cache_pool", None)
    if raw_cache_pool is not None:
        budget = WorkflowCachePoolBudgetIr(
            max_entries=int(raw_cache_pool.budget.max_entries),
            over_budget_policy=str(raw_cache_pool.budget.over_budget_policy),
        )
        pins = tuple(WorkflowCachePoolPinIr(kind=str(pin.kind), source_id=str(pin.source_id)) for pin in (raw_cache_pool.pin or ()))
        cache_pool = WorkflowCachePoolIr(
            conflict_policy=str(raw_cache_pool.conflict_policy),
            release_policy=str(raw_cache_pool.release_policy),
            budget=budget,
            pin=pins,
        )

    raw_ctx = getattr(wf_obj.options, "ctx", None)
    ctx = WorkflowCtxOptionsIr()
    if raw_ctx is not None:
        ctx = WorkflowCtxOptionsIr(
            max_value_bytes=int(raw_ctx.max_value_bytes),
            max_bytes=int(raw_ctx.max_bytes),
        )

    workflow_options = WorkflowOptionsIr(
        max_concurrency=int(wf_obj.options.max_concurrency),
        failure_policy=str(wf_obj.options.failure_policy or "all_fail"),
        cache_pool=cache_pool,
        ctx=ctx,
    )

    artifacts = WorkflowArtifactsIr(slots_by_node_id=slots_by_node_id)
    resources_sorted = sorted(resources, key=lambda r: (str(r.resource_type), str(r.resource_id)))
    return WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=workflow_options,
        resources=tuple(resources_sorted),
        artifacts=artifacts,
    )


def derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
    *,
    template_vars: Optional[Mapping[str, object]],
    allowed_yaml_roots: Optional[Tuple[str, ...]],
) -> Tuple[Dict[str, FrozenSet[Tuple[str, str]]], Dict[Tuple[str, str], FrozenSet[str]]]:
    """基于 `workflow IR` + `demand YAML` 推导缓存消费者集合上界.

    `v0`: 仅覆盖 `cache_mode=preload_forever` 的 `sources`,按 `(kind, source_id)` 聚合.
    """

    loader = YamlDemandLoader()

    logical_keys_by_node_id: Dict[str, FrozenSet[Tuple[str, str]]] = {}
    consumers_by_logical_key: Dict[Tuple[str, str], Set[str]] = {}

    for node in workflow_ir.nodes:
        node_id = str(node.node_id)
        keys: Set[Tuple[str, str]] = set()
        demand_path = getattr(node, "demand_path", None)
        if demand_path is not None:
            config = loader.load(str(demand_path), template_vars=template_vars, allowed_yaml_roots=allowed_yaml_roots)
            for source_id, source in getattr(config, "sources", {}).items():
                if str(getattr(source, "cache_mode", "") or "") != "preload_forever":
                    continue
                logical_key = ("preload_forever", str(source_id))
                keys.add(logical_key)
                consumers_by_logical_key.setdefault(logical_key, set()).add(node_id)

        logical_keys_by_node_id[node_id] = frozenset(keys)

    consumers_frozen = {key: frozenset(sorted(node_ids)) for key, node_ids in consumers_by_logical_key.items()}
    return logical_keys_by_node_id, consumers_frozen


__all__ = [
    "compile_workflow_ir",
    "derive_cache_pool_consumers",
]
