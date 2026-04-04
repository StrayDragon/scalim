"""`workflow` 运行入口(稳定导入路径).

说明:
- 该模块对外保持稳定导入路径,内部实现可迁移/拆分.
- 该模块属于 `YAML` `DSL` 适配层:负责加载/校验/编译 `workflow` `YAML`,并通过回调调用框架层 `scalim.workflow` 的统一执行入口.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Callable, Dict, FrozenSet, List, Mapping, Optional, Tuple, Union

from ...execution.run_ir import ExecutionResult
from ...spec.ir._workflow import WorkflowIr, WorkflowNodeIr
from ...typedefs import KeyNormalizationMode, ParallelMode
from ...vendor.compact.typing_extensionsx import Protocol
from ...vendor.dataclassesx import replace
from ...workflow.execute import ScalimWorkflowRunFailedError
from ...workflow.execute import run_workflow_ir as _run_workflow_ir
from ...workflow.report import WorkflowResult
from ._internal.config_parsing.template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN
from ._public_template_sandbox import validate_public_template_sandbox
from .runtime.compiler import compile as _compile_demand_default
from .runtime.contracts import (
    UNSET,
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    DemandDiagnosticsOverride,
    DemandDiagnosticsPolicy,
    FileResourceOverride,
    ResourcesOverride,
    RunOptions,
    RunOverrides,
    RunResult,
    UnsetType,
)
from .schema_dsl.models import BookConfig, DemandConfig, FileConfig, ResourcesConfig
from .workflow import ScalimWorkflowConfigError, WorkflowConfig
from .workflow_compile import compile_workflow_ir, derive_cache_pool_consumers
from .workflow_load import load_workflow_config_from_path
from .workflow_preflight import WORKFLOW_PREFLIGHT_CHECKS, WorkflowPreflightContext, WorkflowPreflightRun, run_workflow_preflight
from .workflow_types import ComponentsExtend, ComponentsInherit, ComponentsReplace, WorkflowRunPatch

_WORKFLOW_BUNDLE_VIZ_REQUIRES_OVERRIDES_MSG = "workflow bundle viz requires run_workflow(..., overrides=RunOverrides(viz_config=...))"


def _merge_book_budget_overrides(
    left: Optional[BookBudgetOverride],
    right: Optional[BookBudgetOverride],
) -> Optional[BookBudgetOverride]:
    if right is None:
        return left
    if left is None:
        return right
    return BookBudgetOverride(
        max_sheets=left.max_sheets if right.max_sheets is None else right.max_sheets,
        max_total_cells=left.max_total_cells if right.max_total_cells is None else right.max_total_cells,
    )


def _merge_book_export_xlsx_overrides(
    left: Optional[BookExportXlsxOverride],
    right: Optional[BookExportXlsxOverride],
) -> Optional[BookExportXlsxOverride]:
    if right is None:
        return left
    if left is None:
        return right
    return BookExportXlsxOverride(
        path=left.path if right.path is None else right.path,
        write_lock=left.write_lock if right.write_lock is None else right.write_lock,
        allow_formulas=left.allow_formulas if right.allow_formulas is None else right.allow_formulas,
    )


def _merge_book_write_defaults_overrides(
    left: Optional[BookWriteDefaultsOverride],
    right: Optional[BookWriteDefaultsOverride],
) -> Optional[BookWriteDefaultsOverride]:
    if right is None:
        return left
    if left is None:
        return right
    return BookWriteDefaultsOverride(
        mode=left.mode if right.mode is None else right.mode,
        align_by=left.align_by if right.align_by is None else right.align_by,
        header_policy=left.header_policy if right.header_policy is None else right.header_policy,
        on_mismatch=left.on_mismatch if right.on_mismatch is None else right.on_mismatch,
        on_conflict=left.on_conflict if right.on_conflict is None else right.on_conflict,
    )


def _merge_book_resource_overrides(left: Optional[BookResourceOverride], right: BookResourceOverride) -> BookResourceOverride:
    if left is None:
        return right
    return BookResourceOverride(
        kind=left.kind if right.kind is None else right.kind,
        path=left.path if right.path is None else right.path,
        budget=_merge_book_budget_overrides(left.budget, right.budget),
        export_xlsx=_merge_book_export_xlsx_overrides(left.export_xlsx, right.export_xlsx),
        allow_formulas=left.allow_formulas if right.allow_formulas is None else right.allow_formulas,
        write_lock=left.write_lock if right.write_lock is None else right.write_lock,
        write_defaults=_merge_book_write_defaults_overrides(left.write_defaults, right.write_defaults),
    )


def _merge_file_resource_overrides(left: Optional[FileResourceOverride], right: FileResourceOverride) -> FileResourceOverride:
    if left is None:
        return right
    return FileResourceOverride(
        kind=left.kind if right.kind is None else right.kind,
        path=left.path if right.path is None else right.path,
        encoding=left.encoding if right.encoding is None else right.encoding,
    )


def _merge_resources_overrides(
    workflow_override: Optional[ResourcesOverride],
    user_override: Optional[ResourcesOverride],
) -> Optional[ResourcesOverride]:
    if workflow_override is None:
        return user_override
    if user_override is None:
        return workflow_override

    merged_books: Dict[str, BookResourceOverride] = dict(workflow_override.books or {})
    merged_files: Dict[str, FileResourceOverride] = dict(workflow_override.files or {})

    for book_id, book_override in (user_override.books or {}).items():
        merged_books[str(book_id)] = _merge_book_resource_overrides(merged_books.get(str(book_id)), book_override)
    for file_id, file_override in (user_override.files or {}).items():
        merged_files[str(file_id)] = _merge_file_resource_overrides(merged_files.get(str(file_id)), file_override)

    return ResourcesOverride(books=merged_books or None, files=merged_files or None)


def _book_config_to_resource_override(book: BookConfig) -> BookResourceOverride:
    kind = str(book.kind or "").strip() or None

    budget_override = None
    if book.budget is not None:
        budget_override = BookBudgetOverride(
            max_sheets=int(book.budget.max_sheets),
            max_total_cells=int(book.budget.max_total_cells),
        )

    export_override = None
    if book.export_xlsx is not None:
        export_override = BookExportXlsxOverride(
            path=book.export_xlsx.path,
            write_lock=True if bool(book.export_xlsx.write_lock) else None,
            allow_formulas=True if bool(book.export_xlsx.allow_formulas) else None,
        )

    write_defaults_override = None
    if book.write_defaults is not None:
        write_defaults_override = BookWriteDefaultsOverride(
            mode=str(book.write_defaults.mode or ""),
            align_by=str(book.write_defaults.align_by or ""),
            header_policy=str(book.write_defaults.header_policy or ""),
            on_mismatch=str(book.write_defaults.on_mismatch or ""),
            on_conflict=str(book.write_defaults.on_conflict or ""),
        )

    allow_formulas = True if bool(book.allow_formulas) else None
    write_lock = True if bool(book.write_lock) else None

    return BookResourceOverride(
        kind=kind,
        path=book.path if book.path is not None else None,
        budget=budget_override,
        export_xlsx=export_override,
        allow_formulas=allow_formulas,
        write_lock=write_lock,
        write_defaults=write_defaults_override,
    )


def _file_config_to_resource_override(file_cfg: FileConfig) -> FileResourceOverride:
    kind = str(file_cfg.kind or "").strip() or None
    encoding = str(file_cfg.encoding or "").strip() or None
    return FileResourceOverride(kind=kind, path=file_cfg.path if file_cfg.path is not None else None, encoding=encoding)


def _workflow_resources_override(wf: WorkflowConfig) -> Optional[ResourcesOverride]:
    resources = wf.resources
    resources_cfg = resources if isinstance(resources, ResourcesConfig) else None
    if resources_cfg is None:
        return None
    books = dict(resources_cfg.books or {})
    files = dict(resources_cfg.files or {})
    if not books and not files:
        return None

    payload_books = {str(book_id): _book_config_to_resource_override(book) for book_id, book in books.items()} if books else None
    payload_files = {str(file_id): _file_config_to_resource_override(file_cfg) for file_id, file_cfg in files.items()} if files else None
    return ResourcesOverride(books=payload_books, files=payload_files)


def _merge_node_overrides(
    base_overrides: Optional[RunOverrides],
    *,
    workflow_resources_override: Optional[ResourcesOverride],
) -> Optional[RunOverrides]:
    base_resources = None if base_overrides is None else base_overrides.resources
    merged_resources = _merge_resources_overrides(workflow_resources_override, base_resources)

    if base_overrides is None:
        if merged_resources is None:
            return None
        return RunOverrides(resources=merged_resources)

    if merged_resources == base_resources:
        return base_overrides

    return replace(base_overrides, resources=merged_resources)


def _validate_run_patches_by_id(
    patches: Optional[Mapping[str, object]],
    *,
    known_run_ids: FrozenSet[str],
) -> Optional[Mapping[str, WorkflowRunPatch]]:
    if patches is None:
        return None
    items = patches.items()

    unknown: List[str] = []
    typed: Dict[str, WorkflowRunPatch] = {}
    for raw_run_id, raw_patch in items:
        if not isinstance(raw_run_id, str):
            msg = "run_patches_by_id keys must be workflow run ids (str)"
            raise TypeError(msg)
        run_id = raw_run_id
        if run_id not in known_run_ids:
            unknown.append(run_id)
            continue

        if isinstance(raw_patch, dict):
            msg = "run_patches_by_id['{}'] must be a typed WorkflowRunPatch (dict patches are not supported). ".format(
                run_id,
            ) + "Example: run_patches_by_id={{'{}': WorkflowRunPatch(batch_size=5000)}}".format(run_id)
            raise TypeError(msg)
        if not isinstance(raw_patch, WorkflowRunPatch):
            msg = "run_patches_by_id['{}'] must be a WorkflowRunPatch".format(run_id)
            raise TypeError(msg)
        typed[run_id] = raw_patch

    if unknown:
        known_ids_text = ", ".join(sorted(known_run_ids))
        msg = "Unknown workflow run id(s) in run_patches_by_id: {}. Known run ids: {}".format(", ".join(sorted(unknown)), known_ids_text)
        raise ScalimWorkflowConfigError(msg, path="run_workflow.run_patches_by_id")

    return typed


def _apply_workflow_run_patch_demand_diagnostics(base: RunOptions, patch: WorkflowRunPatch) -> RunOptions:
    demand_diagnostics = patch.demand_diagnostics
    if isinstance(demand_diagnostics, UnsetType):
        return base
    if demand_diagnostics is None:
        return replace(base, demand_diagnostics=None)

    if not isinstance(demand_diagnostics, DemandDiagnosticsOverride):
        msg = "WorkflowRunPatch.demand_diagnostics must be a DemandDiagnosticsOverride or None"
        raise TypeError(msg)
    if isinstance(demand_diagnostics.include_full_error_message, UnsetType) and isinstance(
        demand_diagnostics.validate_unique_field_names, UnsetType
    ):
        return base

    base_policy = base.demand_diagnostics
    base_include_full = False if base_policy is None else bool(base_policy.include_full_error_message)
    base_validate_unique = True if base_policy is None else bool(base_policy.validate_unique_field_names)

    include_full_error_message = (
        base_include_full
        if isinstance(demand_diagnostics.include_full_error_message, UnsetType)
        else bool(demand_diagnostics.include_full_error_message)
    )
    validate_unique_field_names = (
        base_validate_unique
        if isinstance(demand_diagnostics.validate_unique_field_names, UnsetType)
        else bool(demand_diagnostics.validate_unique_field_names)
    )

    return replace(
        base,
        demand_diagnostics=DemandDiagnosticsPolicy(
            include_full_error_message=include_full_error_message,
            validate_unique_field_names=validate_unique_field_names,
        ),
    )


def _apply_workflow_run_patch(base: RunOptions, patch: WorkflowRunPatch) -> RunOptions:
    next_options = base

    batch_size = patch.batch_size
    if not isinstance(batch_size, UnsetType):
        next_options = replace(next_options, batch_size=batch_size)

    demand_failure_policy = patch.demand_failure_policy
    if not isinstance(demand_failure_policy, UnsetType):
        next_options = replace(next_options, demand_failure_policy=demand_failure_policy)

    next_options = _apply_workflow_run_patch_demand_diagnostics(next_options, patch)

    guardrails = patch.guardrails
    if not isinstance(guardrails, UnsetType):
        next_options = replace(next_options, guardrails=guardrails)

    loader_retry = patch.loader_retry
    if not isinstance(loader_retry, UnsetType):
        next_options = replace(next_options, loader_retry=loader_retry)

    overrides = patch.overrides
    if not isinstance(overrides, UnsetType):
        next_options = replace(next_options, overrides=overrides)

    components_patch = patch.components
    if isinstance(components_patch, ComponentsInherit):
        return next_options
    if isinstance(components_patch, ComponentsReplace):
        return replace(next_options, components=list(components_patch.items))
    if isinstance(components_patch, ComponentsExtend):
        merged = list(next_options.components or [])
        merged.extend(list(components_patch.items))
        return replace(next_options, components=merged)

    msg = "WorkflowRunPatch.components must be one of ComponentsInherit/ComponentsReplace/ComponentsExtend"
    raise TypeError(msg)


if TYPE_CHECKING:
    from ...execution.guardrails import GuardrailsPolicy
    from ...execution.loader_retry import LoaderRetryPoliciesSpec
    from ...hooks import IExecutionHook
    from ...ob.observer import Observer
    from ...ob.presets.viz import VizObserverConfig
    from .workflow_config._models import WorkflowOutputStagingOptions, WorkflowResourcesWaitOptions


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


def _compile_demand_node_impl(
    demand_path: str,
    *,
    workflow_exec_id: str,
    workflow_node_id: str,
    workflow_node_decl_order: int,
    node_init_vars: Dict[str, object],
    managed_output_ids: Optional[FrozenSet[str]],
    viz_config: Optional["VizObserverConfig"],
    base_options: RunOptions,
    workflow_resources_override: Optional[ResourcesOverride],
    run_patches_by_id: Optional[Mapping[str, WorkflowRunPatch]],
    compile_demand: Callable[..., _CompilationLike],
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
            raise ScalimWorkflowConfigError(
                _WORKFLOW_BUNDLE_VIZ_REQUIRES_OVERRIDES_MSG,
                path="run_workflow.overrides.viz_config",
            )  # pragma: no cover  # pragma: allow-no-cover invariant: viz_config requires overrides
        base_overrides = replace(
            base_overrides,
            viz_config=viz_config,
        )
        node_options = replace(node_options, overrides=base_overrides)

    if run_patches_by_id is not None:
        patch = run_patches_by_id.get(str(workflow_node_id))
        if patch is not None:
            node_options = _apply_workflow_run_patch(node_options, patch)

    merged_overrides = _merge_node_overrides(
        node_options.overrides,
        workflow_resources_override=workflow_resources_override,
    )
    if merged_overrides is not node_options.overrides:
        node_options = replace(node_options, overrides=merged_overrides)

    if managed_output_ids:
        node_options = replace(node_options, workflow_managed_output_ids=managed_output_ids)

    return compile_demand(str(demand_path), options=node_options)


def _build_demand_run_result_impl(
    core: ExecutionResult,
    *,
    compilation: _CompilationLike,
    demand_yaml_path: str,
    workflow_exec_id: str,
    workflow_node_id: str,
) -> object:
    _ = workflow_exec_id, workflow_node_id
    return RunResult(core, config=compilation.config, yaml_path=str(demand_yaml_path), sink=None)


def _run_workflow_preflight_or_raise(
    workflow_path: str,
    workflow_ir: WorkflowIr,
    *,
    base_options: RunOptions,
    workflow_resources_override: Optional[ResourcesOverride],
    run_patches_by_id: Optional[Mapping[str, WorkflowRunPatch]],
) -> None:
    preflight_runs: List[WorkflowPreflightRun] = []
    for node in workflow_ir.nodes:
        if not isinstance(node, WorkflowNodeIr):
            continue

        node_options = base_options
        if node.init_vars:
            merged = dict(base_options.init_vars or {})
            merged.update(dict(node.init_vars))
            node_options = replace(node_options, init_vars=merged)

        if run_patches_by_id is not None:
            patch = run_patches_by_id.get(str(node.node_id))
            if patch is not None:
                node_options = _apply_workflow_run_patch(node_options, patch)

        merged_overrides = _merge_node_overrides(
            node_options.overrides,
            workflow_resources_override=workflow_resources_override,
        )
        if merged_overrides is not node_options.overrides:
            node_options = replace(node_options, overrides=merged_overrides)

        preflight_runs.append(
            WorkflowPreflightRun(
                run_id=str(node.node_id),
                demand_path=str(node.demand_path),
                decl_order=int(node.decl_order),
                options=node_options,
            )
        )

    run_workflow_preflight(
        WorkflowPreflightContext(workflow_yaml_path=str(workflow_path)),
        runs=preflight_runs,
        checks=WORKFLOW_PREFLIGHT_CHECKS,
    )


def run_workflow(  # noqa: PLR0913
    workflow_yaml_path: str,
    *,
    allowed_modules: FrozenSet[str],
    allowed_functions: Optional[FrozenSet[str]] = None,
    components: Optional[List[Union["Observer", "IExecutionHook"]]] = None,
    overrides: Optional[RunOverrides] = None,
    guardrails: Optional["GuardrailsPolicy"] = None,
    loader_retry: Optional["LoaderRetryPoliciesSpec"] = None,
    batch_size: Union[Optional[int], UnsetType] = UNSET,
    run_patches_by_id: Optional[Mapping[str, WorkflowRunPatch]] = None,
    demand_failure_policy: Optional[str] = None,
    demand_diagnostics: Optional[DemandDiagnosticsPolicy] = None,
    workflow_resources_wait: Optional["WorkflowResourcesWaitOptions"] = None,
    workflow_output_staging: Optional["WorkflowOutputStagingOptions"] = None,
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
        overrides=overrides,
        workflow_resources_wait=workflow_resources_wait,
        workflow_output_staging=workflow_output_staging,
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
        demand_failure_policy=demand_failure_policy,
        demand_diagnostics=demand_diagnostics,
        parallel_mode=parallel_mode,
        max_workers=int(max_workers),
        key_normalization=key_normalization,
        init_vars=init_vars,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    workflow_resources_override = _workflow_resources_override(wf)
    run_ids = frozenset(run.id for run in wf.runs)
    run_patches_by_id = _validate_run_patches_by_id(run_patches_by_id, known_run_ids=run_ids)

    # 4.5) `workflow` 预检查(`preflight`):运行期但可推理的诊断;快速失败
    _run_workflow_preflight_or_raise(
        str(workflow_path),
        workflow_ir,
        base_options=base_options,
        workflow_resources_override=workflow_resources_override,
        run_patches_by_id=run_patches_by_id,
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
        return _compile_demand_node_impl(
            demand_path,
            workflow_exec_id=workflow_exec_id,
            workflow_node_id=workflow_node_id,
            workflow_node_decl_order=workflow_node_decl_order,
            node_init_vars=node_init_vars,
            managed_output_ids=managed_output_ids,
            viz_config=viz_config,
            base_options=base_options,
            workflow_resources_override=workflow_resources_override,
            run_patches_by_id=run_patches_by_id,
            compile_demand=compile_demand,
        )

    def _build_demand_run_result(
        core: ExecutionResult,
        *,
        compilation: _CompilationLike,
        demand_yaml_path: str,
        workflow_exec_id: str,
        workflow_node_id: str,
    ) -> object:
        return _build_demand_run_result_impl(
            core,
            compilation=compilation,
            demand_yaml_path=demand_yaml_path,
            workflow_exec_id=workflow_exec_id,
            workflow_node_id=workflow_node_id,
        )

    # 5) 执行 `workflow` `IR`(框架层)
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


__all__ = (
    "ScalimWorkflowRunFailedError",
    "WorkflowResult",
    "run_workflow",
)
