"""`workflow` 运行入口(稳定导入路径).

说明:
- 该模块对外保持稳定导入路径,内部实现可迁移/拆分.
- 该模块属于 `YAML` `DSL` 适配层:负责加载/校验/编译 `workflow` `YAML`,并通过回调调用框架层 `scalim.workflow` 的统一执行入口.
- 运行时需兼容 `Python 3.6`.
"""

from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from ...execution.run_ir import ExecutionResult
from ...vendor.dataclassesx import replace
from ...workflow.errors import WorkflowConfigError as WorkflowRuntimeConfigError
from ...workflow.execute import WorkflowRunFailedError
from ...workflow.execute import run_workflow_ir as _run_workflow_ir
from ...workflow.report import WorkflowResult
from ._public_template_sandbox import validate_public_template_sandbox
from .runtime.compiler import compile as _compile_demand_default
from .runtime.contracts import UNSET, RunOptions, RunOverrides, RunResult
from .runtime.output_composition_yaml import PathlessCsvOutputError
from .runtime.output_path_resolve import resolve_output_container_path
from .workflow import WorkflowConfigError
from .workflow_compile import compile_workflow_ir, derive_cache_pool_consumers
from .workflow_load import load_workflow_config_from_path


def _extract_bundle_viz_base_config(overrides: Optional[RunOverrides]) -> Optional[object]:
    # 工作流 `bundle` 可视化: 通过 `run_workflow(..., overrides=RunOverrides(viz_config=...))` 显式启用.
    bundle_viz_base_config: Optional[object] = None
    if overrides is not None and overrides.viz_config is not UNSET:
        viz_override = cast("Any", overrides.viz_config)
        if viz_override is not None:
            bundle_viz_base_config = viz_override
            if getattr(bundle_viz_base_config, "has_explicit_paths", lambda: False)():
                msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`(请勿设置 `output_path`/`snapshot_path`/`trace_path`)."
                raise WorkflowConfigError(msg, path="run_workflow.overrides.viz_config")
            output_dir = getattr(bundle_viz_base_config, "output_dir", None)
            use_default_output_dir = bool(getattr(bundle_viz_base_config, "use_default_output_dir", False))
            if not output_dir and not use_default_output_dir:
                msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`, 或设置 `use_default_output_dir=True`."
                raise WorkflowConfigError(msg, path="run_workflow.overrides.viz_config")
    return bundle_viz_base_config


def run_workflow(  # noqa: PLR0913, C901, PLR0915
    workflow_yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    components: Optional[List[object]] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional[object] = None,
    loader_retry: Optional[object] = None,
    batch_size: Optional[int] = None,
    parallel_mode: str = "seq",
    max_workers: int = 0,
    key_normalization: str = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    path_aliases: Optional[Mapping[str, str]] = None,
    run_ir_fn: Optional[Callable[..., ExecutionResult]] = None,
    compile_demand_yaml_fn: Optional[Callable[..., object]] = None,
) -> WorkflowResult:
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    # 1) 加载并编译 `workflow` `YAML` -> `IR`(`DSL` 层)
    workflow_path, wf = load_workflow_config_from_path(
        workflow_yaml_path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
    )
    workflow_ir = compile_workflow_ir(
        wf,
        workflow_yaml_path=workflow_path,
        path_aliases=path_aliases,
        template_vars=template_vars,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    # 2) 推导 `workflow` 缓存池消费关系上界(`DSL` 层;依赖 `demand` `YAML`)
    cache_pool_logical_keys_by_node_id = None
    cache_pool_consumers_by_logical_key = None
    if workflow_ir.options.cache_pool is not None:
        cache_pool_logical_keys_by_node_id, cache_pool_consumers_by_logical_key = derive_cache_pool_consumers(
            workflow_ir,
            template_vars=template_vars,
            allowed_yaml_roots=allowed_yaml_roots,
        )

    # 3) 解析 `bundle` 可视化配置(`DSL` 层;依赖 `RunOverrides`/`UNSET`)
    bundle_viz_base_config = _extract_bundle_viz_base_config(overrides)

    # 4) 每个 `node` 的 `demand` 编译回调 + 结果组装器(保持 `API` 稳定)
    base_options = RunOptions(
        allowed_modules=allowed_modules,
        allowed_functions=allowed_functions,
        components=cast("Any", components),
        sink=None,
        output_composition=None,
        overrides=overrides,
        guardrails=cast("Any", guardrails),
        loader_retry=cast("Any", loader_retry),
        batch_size=batch_size,
        parallel_mode=cast("Any", parallel_mode),
        max_workers=int(max_workers),
        key_normalization=cast("Any", key_normalization),
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    reserved_xlsx_paths: Set[str] = set()
    for res in workflow_ir.resources:
        if str(getattr(res, "resource_type", "")) not in {"workbook", "sheetbook"}:
            continue
        res_path = str(getattr(res, "path", "") or "").strip()
        if not res_path:
            continue
        reserved_xlsx_paths.add(str(Path(res_path).expanduser().resolve(strict=False)))
    workbook_writers_by_abs_path: Dict[str, List[str]] = {}

    def _as_abs_path(raw_path: str) -> str:
        return str(Path(str(raw_path)).expanduser().resolve(strict=False))

    def _collect_workbook_output_paths(cfg: object, *, init_vars: Optional[Dict[str, object]]) -> Set[str]:
        raw_paths: Set[str] = set()

        default_workbook_path: Optional[str] = None
        for idx, out_cfg in enumerate(getattr(cfg, "outputs", ()) or ()):
            container = getattr(out_cfg, "container", None)
            if container is None:
                continue  # pragma: no cover
            if str(getattr(container, "type", "") or "").lower() != "workbook":
                continue
            path_str = resolve_output_container_path(
                getattr(container, "path", None),
                init_vars=init_vars,
                path="outputs.{}.container.path".format(int(idx)),
            )
            raw_paths.add(path_str)
            if default_workbook_path is None:
                default_workbook_path = path_str

        for extra in (getattr(cfg, "meta", None), getattr(cfg, "audit", None)):
            if extra is None:
                continue
            p = str(getattr(extra, "path", "") or "").strip()
            if p:
                raw_paths.add(p)
            elif default_workbook_path:
                raw_paths.add(default_workbook_path)

        abs_paths: Set[str] = set()
        for raw_path in raw_paths:
            abs_paths.add(_as_abs_path(str(raw_path)))
        return abs_paths

    def _precheck_and_register_workbook_output_paths(
        *,
        run_id: str,
        demand_config: object,
        init_vars: Optional[Dict[str, object]],
    ) -> None:
        abs_paths = _collect_workbook_output_paths(demand_config, init_vars=init_vars)
        for abs_path in sorted(abs_paths):
            if abs_path in reserved_xlsx_paths:
                msg = (
                    "Excel output path is reserved by workflow shared resources (use resources + write nodes): "
                    + "run_id={!r}, path={!r}".format(str(run_id), str(abs_path))
                )
                raise WorkflowRuntimeConfigError(msg, path="workflow.runs[*].demand")

            existing = workbook_writers_by_abs_path.get(abs_path)
            if existing is not None and str(run_id) not in existing:
                nodes = list(existing)
                nodes.append(str(run_id))
                msg = "Excel output path collision across workflow nodes: run_id={!r}, path={!r}, nodes={}".format(
                    str(run_id),
                    str(abs_path),
                    ",".join(nodes),
                )
                raise WorkflowRuntimeConfigError(msg, path="workflow.runs[*].demand")

            if existing is None:
                workbook_writers_by_abs_path[abs_path] = [str(run_id)]

    compile_demand_yaml_fn = compile_demand_yaml_fn or _compile_demand_default

    def _compile_demand_node(
        demand_path: str,
        *,
        workflow_exec_id: str,
        workflow_node_id: str,
        workflow_node_decl_order: int,
        node_init_vars: Dict[str, object],
        managed_output_ids: Optional[FrozenSet[str]],
        viz_config: Optional[object],
    ) -> object:
        _ = workflow_exec_id, workflow_node_decl_order
        node_options = base_options
        if node_init_vars:
            merged = dict(base_options.init_vars or {})
            merged.update(node_init_vars)
            node_options = replace(node_options, init_vars=merged)

        if viz_config is not None:
            base_overrides = cast("Any", node_options.overrides)
            if base_overrides is None:
                msg = "workflow bundle viz requires run_workflow(..., overrides=RunOverrides(viz_config=...))"  # pragma: no cover
                raise WorkflowRuntimeConfigError(msg, path="run_workflow.overrides.viz_config")  # pragma: no cover
            base_overrides = replace(cast("RunOverrides", base_overrides), viz_config=viz_config)
            node_options = replace(node_options, overrides=base_overrides)

        if managed_output_ids:
            node_options = replace(node_options, workflow_managed_output_ids=managed_output_ids)

        try:
            compilation = compile_demand_yaml_fn(str(demand_path), options=node_options)
        except PathlessCsvOutputError as exc:
            msg = "run_id={!r}: {}".format(str(workflow_node_id), str(exc))
            raise WorkflowRuntimeConfigError(msg, path=str(exc.config_path)) from exc

        _precheck_and_register_workbook_output_paths(
            run_id=str(workflow_node_id),
            demand_config=getattr(compilation, "config", None),
            init_vars=getattr(node_options, "init_vars", None),
        )
        return compilation

    def _build_demand_run_result(
        core: ExecutionResult,
        *,
        compilation: object,
        demand_yaml_path: str,
        workflow_exec_id: str,
        workflow_node_id: str,
    ) -> object:
        _ = workflow_exec_id, workflow_node_id
        comp = cast("Any", compilation)
        return RunResult(core, config=comp.config, yaml_path=str(demand_yaml_path), sink=None)

    # 5) 执行 `workflow` `IR`(框架层)
    try:
        return _run_workflow_ir(
            workflow_path,
            workflow_ir,
            compile_demand_fn=_compile_demand_node,
            build_demand_run_result_fn=_build_demand_run_result,
            run_ir_fn=run_ir_fn,
            components=components,
            bundle_viz_base_config=cast("Any", bundle_viz_base_config),
            cache_pool_logical_keys_by_node_id=cache_pool_logical_keys_by_node_id,
            cache_pool_consumers_by_logical_key=cache_pool_consumers_by_logical_key,
        )
    except WorkflowRuntimeConfigError as exc:
        # 将框架层 `WorkflowConfigError` 回写为 `DSL` 层错误类型(保持对外契约).
        path = str(getattr(exc, "path", "") or "")
        msg = str(exc)
        if path:
            suffix = " (path={})".format(path)
            if msg.endswith(suffix):
                msg = msg[: -len(suffix)]
        raise WorkflowConfigError(msg, path=path) from exc


__all__ = [
    "WorkflowResult",
    "WorkflowRunFailedError",
    "run_workflow",
]
