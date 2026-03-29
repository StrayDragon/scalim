"""`workflow` 运行入口(稳定导入路径).

说明:
- 该模块对外保持稳定导入路径,内部实现可迁移/拆分.
- 该模块属于 `YAML` `DSL` 适配层:负责加载/校验/编译 `workflow` `YAML`,并通过回调调用框架层 `scalim.workflow` 的统一执行入口.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

from ...execution.run_ir import ExecutionResult
from ...typedefs import KeyNormalizationMode, ParallelMode
from ...vendor.compact.typing_extensionsx import Protocol
from ...vendor.dataclassesx import replace
from ...workflow.errors import ScalimWorkflowConfigError as WorkflowRuntimeConfigError
from ...workflow.execute import ScalimWorkflowRunFailedError
from ...workflow.execute import run_workflow_ir as _run_workflow_ir
from ...workflow.report import WorkflowResult
from ._public_template_sandbox import validate_public_template_sandbox
from .config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from .runtime.compiler import compile as _compile_demand_default
from .runtime.contracts import RunOptions, RunOverrides, RunResult, UnsetType
from .schema_dsl.models import DemandConfig
from .workflow import ScalimWorkflowConfigError
from .workflow_compile import compile_workflow_ir, derive_cache_pool_consumers
from .workflow_load import load_workflow_config_from_path

_WORKFLOW_BUNDLE_VIZ_REQUIRES_OVERRIDES_MSG = "workflow bundle viz requires run_workflow(..., overrides=RunOverrides(viz_config=...))"

if TYPE_CHECKING:
    from ...execution.guardrails import GuardrailsPolicy
    from ...execution.loader_retry import LoaderRetryPoliciesSpec
    from ...hooks import IExecutionHook
    from ...ob.observer import Observer
    from ...ob.presets.viz import VizObserverConfig


class _CompilationLike(Protocol):
    @property
    def config(self) -> DemandConfig: ...


def _extract_bundle_viz_base_config(overrides: Optional[RunOverrides]) -> Optional["VizObserverConfig"]:
    # 工作流 `bundle` 可视化: 通过 `run_workflow(..., overrides=RunOverrides(viz_config=...))` 显式启用.
    if overrides is None:
        return None
    viz_config = overrides.viz_config
    if viz_config is None or isinstance(viz_config, UnsetType):
        return None

    bundle_viz_base_config: "VizObserverConfig" = viz_config
    if getattr(bundle_viz_base_config, "has_explicit_paths", lambda: False)():  # pragma: allow-dynattr optional-interface: viz_config
        msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`(请勿设置 `output_path`/`snapshot_path`/`trace_path`)."
        raise ScalimWorkflowConfigError(msg, path="run_workflow.overrides.viz_config")
    output_dir = getattr(bundle_viz_base_config, "output_dir", None)  # pragma: allow-dynattr optional-interface: viz_config
    use_default_output_dir = bool(
        getattr(bundle_viz_base_config, "use_default_output_dir", False)  # pragma: allow-dynattr optional-interface: viz_config
    )
    if not output_dir and not use_default_output_dir:
        msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`, 或设置 `use_default_output_dir=True`."
        raise ScalimWorkflowConfigError(msg, path="run_workflow.overrides.viz_config")
    return bundle_viz_base_config


def run_workflow(  # noqa: PLR0913, C901
    workflow_yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    components: Optional[List[Union["Observer", "IExecutionHook"]]] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional["GuardrailsPolicy"] = None,
    loader_retry: Optional["LoaderRetryPoliciesSpec"] = None,
    batch_size: Optional[int] = None,
    parallel_mode: ParallelMode = "seq",
    max_workers: int = 0,
    key_normalization: KeyNormalizationMode = "raw",
    init_vars: Optional[Dict[str, object]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    path_aliases: Optional[Mapping[str, str]] = None,
    run_ir_fn: Optional[Callable[..., ExecutionResult]] = None,
    compile_demand_yaml_fn: Optional[Callable[..., _CompilationLike]] = None,
) -> WorkflowResult:
    template_sandbox = validate_public_template_sandbox(template_sandbox)
    # 1) 加载并编译 `workflow` `YAML` -> `IR`(`DSL` 层)
    workflow_path, wf = load_workflow_config_from_path(
        workflow_yaml_path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
    )
    workflow_ir = compile_workflow_ir(
        wf,
        workflow_yaml_path=workflow_path,
        path_aliases=path_aliases,
        template_vars=template_vars,
        allowed_yaml_roots=allowed_yaml_roots,
        init_vars=init_vars,
        overrides=(
            None
            if overrides is None
            else {
                "outputs": overrides.outputs,
                "resources": overrides.resources,
                "outputs_defaults": overrides.outputs_defaults,
            }
        ),
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
        components=components,
        sink=None,
        overrides=overrides,
        guardrails=guardrails,
        loader_retry=loader_retry,
        batch_size=batch_size,
        parallel_mode=parallel_mode,
        max_workers=int(max_workers),
        key_normalization=key_normalization,
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    if compile_demand_yaml_fn is None:
        compile_demand_yaml_fn = _compile_demand_default
    compile_demand = compile_demand_yaml_fn

    def _compile_demand_node(
        demand_path: str,
        *,
        workflow_exec_id: str,
        workflow_node_id: str,
        workflow_node_decl_order: int,
        node_init_vars: Dict[str, object],
        managed_output_ids: Optional[FrozenSet[str]],
        viz_config: Optional["VizObserverConfig"],
    ) -> _CompilationLike:
        _ = workflow_exec_id, workflow_node_id, workflow_node_decl_order
        node_options = base_options
        if node_init_vars:
            merged = dict(base_options.init_vars or {})
            merged.update(node_init_vars)
            node_options = replace(node_options, init_vars=merged)

        if viz_config is not None:
            base_overrides = node_options.overrides
            if base_overrides is None:
                raise WorkflowRuntimeConfigError(
                    _WORKFLOW_BUNDLE_VIZ_REQUIRES_OVERRIDES_MSG,
                    path="run_workflow.overrides.viz_config",
                )  # pragma: no cover  # pragma: allow-no-cover invariant: viz_config requires overrides
            base_overrides = replace(
                base_overrides,
                viz_config=viz_config,
            )
            node_options = replace(node_options, overrides=base_overrides)

        if managed_output_ids:
            node_options = replace(node_options, workflow_managed_output_ids=managed_output_ids)

        return compile_demand(str(demand_path), options=node_options)

    def _build_demand_run_result(
        core: ExecutionResult,
        *,
        compilation: _CompilationLike,
        demand_yaml_path: str,
        workflow_exec_id: str,
        workflow_node_id: str,
    ) -> object:
        _ = workflow_exec_id, workflow_node_id
        return RunResult(core, config=compilation.config, yaml_path=str(demand_yaml_path), sink=None)

    # 5) 执行 `workflow` `IR`(框架层)
    try:
        return _run_workflow_ir(
            workflow_path,
            workflow_ir,
            compile_demand_fn=_compile_demand_node,
            build_demand_run_result_fn=_build_demand_run_result,
            run_ir_fn=run_ir_fn,
            components=components,
            bundle_viz_base_config=bundle_viz_base_config,
            cache_pool_logical_keys_by_node_id=cache_pool_logical_keys_by_node_id,
            cache_pool_consumers_by_logical_key=cache_pool_consumers_by_logical_key,
        )
    except WorkflowRuntimeConfigError as exc:
        # 将框架层 `ScalimWorkflowConfigError` 回写为 `DSL` 层错误类型(保持对外契约).
        path = str(exc.path or "")
        msg = str(exc)
        if path:
            suffix = " (path={})".format(path)
            if msg.endswith(suffix):
                msg = msg[: -len(suffix)]
        raise ScalimWorkflowConfigError(msg, path=path) from exc


__all__ = [
    "ScalimWorkflowRunFailedError",
    "WorkflowResult",
    "run_workflow",
]
