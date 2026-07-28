"""`workflow` 编译阶段编排器 (内部模块).

说明:
- 承载 `WorkflowConfig` -> `WorkflowIr` 的编译流程编排.
- 运行时需兼容 `Python 3.6`.

阶段边界 (职责拆分见 `_internal/workflow_compile_*.py`):
- 图构建: `runs` -> `demand nodes` + `edges` (纯规则; 不读取 `demand YAML`)
- 需求预加载: 读取 `demand YAML` (`filesystem IO`)
- 资源编译: 合并 `resources` + 解析导出路径 (路径解析; 不读取 `demand YAML`)
- 输出注入: 计算有效 `outputs` + 注入写入节点 (纯规则)
- 运行时选项: 选项归一化/校验 -> `OptionsIr` (纯规则)
"""

from pathlib import Path
from typing import Any, Dict, FrozenSet, Mapping, Optional, Set, Tuple, cast

from ...spec.ir._workflow import WorkflowArtifactsIr, WorkflowIr, WorkflowNodeIr
from ...vendor.dataclassesx import dataclass
from ._internal import workflow_compile_graph as _workflow_compile_graph_mod
from ._internal import workflow_compile_options as _workflow_compile_options_mod
from ._internal import workflow_compile_outputs as _workflow_compile_outputs_mod
from ._internal import workflow_compile_resources as _workflow_compile_resources_mod
from ._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from .book_resource_policy import ResourcesPolicy
from .runtime.contracts import RunOverrides
from .schema_dsl.models import DemandConfig
from .workflow import ScalimWorkflowConfigError, WorkflowConfig
from .workflow_types import WorkflowRuntimeOptions


@dataclass(frozen=True)
class WorkflowCompileResult:
    workflow_ir: WorkflowIr
    demand_configs_by_run_id: Dict[str, DemandConfig]


_validate_excel_sheet_name = _workflow_compile_outputs_mod.validate_excel_sheet_name


def _workflow_base_dir(workflow_yaml_path: str) -> Path:
    wf_path = Path(str(workflow_yaml_path or "")).expanduser().resolve(strict=False)
    return wf_path.parent


# 为单元测试/覆盖率提供的内部辅助函数重导出.
# 实现位于 `_internal/workflow_compile_*.py`.
_build_demand_nodes_and_graph = _workflow_compile_graph_mod.build_demand_nodes_and_graph

_as_abs_path = _workflow_compile_resources_mod.as_abs_path
_try_resolve_book_export_abs_path = _workflow_compile_resources_mod.try_resolve_book_export_abs_path
_demand_base_dir = _workflow_compile_resources_mod.demand_base_dir
_book_export_path_and_options = _workflow_compile_resources_mod.book_export_path_and_options
_file_export_path_and_options = _workflow_compile_resources_mod.file_export_path_and_options
_compile_workflow_resources = _workflow_compile_resources_mod.compile_workflow_resources

_outputs_path_ref = _workflow_compile_outputs_mod.outputs_path_ref
_effective_book_binding_for_output = _workflow_compile_outputs_mod.effective_book_binding_for_output
_effective_file_binding_for_output = _workflow_compile_outputs_mod.effective_file_binding_for_output
_effective_sheet_name_for_output = _workflow_compile_outputs_mod.effective_sheet_name_for_output
_effective_write_defaults = _workflow_compile_outputs_mod.effective_write_defaults
_validate_xlsx_memory_align_by = _workflow_compile_outputs_mod.validate_xlsx_memory_align_by
_load_demands = _workflow_compile_outputs_mod.load_demands
_apply_overrides_output_extras = _workflow_compile_outputs_mod.apply_overrides_output_extras
_parse_overrides_outputs_defaults_book_id = _workflow_compile_outputs_mod.parse_overrides_outputs_defaults_book_id
_apply_default_book_binding_to_outputs = _workflow_compile_outputs_mod.apply_default_book_binding_to_outputs
_effective_outputs_for_workflow_compile = _workflow_compile_outputs_mod.effective_outputs_for_workflow_compile
_build_write_node_for_book = _workflow_compile_outputs_mod.build_write_node_for_book
_append_write_nodes_from_runs = _workflow_compile_outputs_mod.append_write_nodes_from_runs
_inject_xlsx_memory_write_dependencies = _workflow_compile_outputs_mod.inject_xlsx_memory_write_dependencies

_normalize_and_validate_workflow_execution_options = _workflow_compile_options_mod.normalize_and_validate_workflow_execution_options
_build_workflow_cache_pool_ir_from_runtime = _workflow_compile_options_mod.build_workflow_cache_pool_ir_from_runtime
_normalize_and_validate_workflow_runtime_options = _workflow_compile_options_mod.normalize_and_validate_workflow_runtime_options
_parse_workflow_option_finite_number = _workflow_compile_options_mod.parse_workflow_option_finite_number
_validate_workflow_resources_wait_override = _workflow_compile_options_mod.validate_workflow_resources_wait_override
_build_workflow_resources_wait_ir = _workflow_compile_options_mod.build_workflow_resources_wait_ir
_normalize_workflow_output_staging_override = _workflow_compile_options_mod.normalize_workflow_output_staging_override
_build_workflow_output_staging_ir = _workflow_compile_options_mod.build_workflow_output_staging_ir
_build_workflow_options_ir = _workflow_compile_options_mod.build_workflow_options_ir


def compile_workflow_ir(
    wf: Any,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    template_vars: Optional[Mapping[str, Any]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Tuple[str, ...]] = None,
    init_vars: Optional[Dict[str, Any]] = None,
    overrides: Optional[Any] = None,
    workflow_runtime_options: Optional[WorkflowRuntimeOptions] = None,
    resources_policy: Optional[ResourcesPolicy] = None,
) -> WorkflowCompileResult:
    """将工作流配置编译为工作流 `IR`.

    说明:
    - `overrides` 为 `RunOverrides` 强类型覆盖项,用于 `resources` 覆盖、`outputs_defaults` 与 `outputs` 替换.
    - `resources_policy` 为 `book` 写入策略 `Python` `SSOT`(可选;缺省 `builtin` `defaults`).
    """
    if overrides is not None and not isinstance(overrides, RunOverrides):
        msg = (
            "overrides must be a RunOverrides (typed dataclasses); legacy YAML-shaped overrides mappings were removed. "
            "Migrate to RunOverrides(outputs=(OutputOverride(...),), "
            "resources=ResourcesOverride(...), outputs_defaults=OutputsDefaultsOverride(...))."
        )
        raise ScalimWorkflowConfigError(msg, path="overrides")
    overrides_typed = overrides
    wf_obj = cast("WorkflowConfig", wf)  # pragma: allow-cast workflow config typed narrowing

    workflow_base_dir = _workflow_base_dir(workflow_yaml_path)

    (
        nodes,
        edges,
        slots_by_node_id,
        demand_yaml_paths_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
    ) = _build_demand_nodes_and_graph(
        wf_obj,
        workflow_yaml_path=workflow_yaml_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    demand_cfg_by_run_id = _load_demands(
        demand_yaml_paths_by_run_id,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    demand_cfg_by_run_id = _apply_overrides_output_extras(demand_cfg_by_run_id, overrides=overrides_typed)

    overrides_resources = None if overrides_typed is None else overrides_typed.resources
    overrides_outputs = None if overrides_typed is None else overrides_typed.outputs
    default_book_id = _parse_overrides_outputs_defaults_book_id(None if overrides_typed is None else overrides_typed.outputs_defaults)

    resources, effective_books, effective_files = _compile_workflow_resources(
        wf_obj,
        workflow_base_dir=workflow_base_dir,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        demand_yaml_paths_by_run_id=demand_yaml_paths_by_run_id,
        init_vars=init_vars,
        overrides_resources=overrides_resources,
    )

    xlsx_memory_write_node_ids_by_run_id = _append_write_nodes_from_runs(
        wf_obj,
        demand_cfg_by_run_id=demand_cfg_by_run_id,
        nodes=nodes,
        edges=edges,
        effective_books=effective_books,
        effective_files=effective_files,
        overrides_outputs=overrides_outputs,
        default_book_id=default_book_id,
        resources_policy=resources_policy,
    )

    _inject_xlsx_memory_write_dependencies(
        xlsx_memory_write_node_ids_by_run_id,
        direct_dependents_by_run_id,
        demand_node_pos_by_run_id,
        nodes,
        edges,
    )

    workflow_options = _build_workflow_options_ir(workflow_runtime_options=workflow_runtime_options)

    artifacts = WorkflowArtifactsIr(slots_by_node_id=slots_by_node_id)
    resources_sorted = sorted(resources, key=lambda r: (str(r.resource_type), str(r.resource_id)))
    workflow_ir = WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=workflow_options,
        resources=tuple(resources_sorted),
        artifacts=artifacts,
    )
    return WorkflowCompileResult(
        workflow_ir=workflow_ir,
        demand_configs_by_run_id=demand_cfg_by_run_id,
    )


def derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
    *,
    demand_configs_by_run_id: Mapping[str, DemandConfig],
) -> Tuple[Dict[str, FrozenSet[Tuple[str, str]]], Dict[Tuple[str, str], FrozenSet[str]]]:
    """基于 `workflow IR` + `demand YAML` 推导缓存消费者集合上界.

    `v0`: 仅覆盖 `cache_mode=preload_forever` 的 `sources`,按 `(kind, source_id)` 聚合.
    """

    logical_keys_by_node_id: Dict[str, FrozenSet[Tuple[str, str]]] = {}
    consumers_by_logical_key: Dict[Tuple[str, str], Set[str]] = {}

    for node in workflow_ir.nodes:
        node_id = str(node.node_id)
        keys: Set[Tuple[str, str]] = set()
        config = demand_configs_by_run_id.get(node_id) if isinstance(node, WorkflowNodeIr) else None
        if config is not None:
            for source_id, source in config.sources.items():
                if str(source.cache_mode or "") != "preload_forever":
                    continue
                logical_key = ("preload_forever", str(source_id))
                keys.add(logical_key)
                consumers_by_logical_key.setdefault(logical_key, set()).add(node_id)

        logical_keys_by_node_id[node_id] = frozenset(keys)

    consumers_frozen = {key: frozenset(sorted(node_ids)) for key, node_ids in consumers_by_logical_key.items()}
    return logical_keys_by_node_id, consumers_frozen


__all__ = (
    "compile_workflow_ir",
    "derive_cache_pool_consumers",
)
