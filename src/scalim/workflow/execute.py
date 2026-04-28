# pragma: allow-c901-file plan: c90
import concurrent.futures
import contextlib
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, cast

from .._internal.utils.json_like import ensure_json_like as _ensure_json_like_ssot
from .._internal.utils.loader_result import normalize_loader_result_policy
from ..events import (
    Event,
    generate_run_id,
)
from ..exceptions import ScalimWorkflowError
from ..execution.adaptive.capture import HookCaptureManager, HookRecordedEvent
from ..execution.run_ir import ExecutionRequest, ExecutionResult, run_ir
from ..execution.workflow_cache_pool import WorkflowCachePool
from ..hooks import HookManager
from ..ob.components import split_components
from ..ob.hub import InstrumentationHub
from ..ob.manager import ObserverManager
from ..ob.observability import Observability
from ..ob.observer import Observer
from ..ob.presets.viz import (
    VizObserverConfig,
    WorkflowVizObserver,
    build_workflow_viz_graph_snapshot,
)
from ..sinks.rows import InMemoryRows, iter_in_memory_rows_as_main_rows
from ..spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WriteSheetNodeIr,
)
from ..typedefs import FailurePolicy, normalize_failure_policy
from ..vendor.compact.typing_extensionsx import TypeGuard
from ..vendor.dataclassesx import dataclass, replace
from . import input_artifacts as _input_artifacts_module
from . import resource_defs as _resource_defs_module
from . import resource_lifecycle as _resource_lifecycle_module
from . import write_nodes as _write_nodes_module
from ._internal.request_overrides import WorkflowNodeRequestOverrides, merge_workflow_node_request
from .artifacts import WorkflowArtifactsDirectory
from .errors import ScalimWorkflowConfigError
from .execute_controller import (
    WorkflowRunController,
)
from .report import WorkflowResult, WorkflowRunError, WorkflowRunOutcome
from .resource_lifecycle import WorkflowResourceLifecycle
from .resources import ScalimWorkflowWriteError, WorkflowResourceManager
from .visibility_index import WorkflowVisibilityIndex
from .viz_reporter import WorkflowVizReporter

_build_workflow_resource_defs = _resource_defs_module.build_workflow_resource_defs
_options_bool = _resource_defs_module.options_bool
_run_workflow_write_sheet_node = _write_nodes_module.run_workflow_write_sheet_node
_run_workflow_append_sheet_node = _write_nodes_module.run_workflow_append_sheet_node
_run_workflow_write_node = _write_nodes_module.run_workflow_write_node
_resolve_workflow_input_csv = _input_artifacts_module.resolve_workflow_input_csv
_resolve_workflow_input_tabular = _input_artifacts_module.resolve_workflow_input_tabular
_resolve_workflow_output_export_header = _input_artifacts_module.resolve_workflow_output_export_header
_commit_workflow_resources = _resource_lifecycle_module.commit_workflow_resources


class _CompilationLike(ABC):
    @property
    @abstractmethod
    def request(self) -> object:
        raise NotImplementedError  # pragma: no cover  # pragma: allow-no-cover abstract property


def ensure_json_like(value: object, *, path: str) -> object:
    return _ensure_json_like_ssot(
        value,
        path=path,
        value_name="ctx value",
        allowed_types_desc="None/bool/int/float/str/list/dict[str, ...]",
        dict_key_desc="non-empty str",
        require_nonempty_dict_key=True,
        error_cls=ScalimWorkflowConfigError,
    )


class WorkflowCtxStore:
    _visible_by_consumer_node_id: Dict[str, FrozenSet[str]]
    _values_by_producer_node_id: Dict[str, Dict[str, object]]
    _owner_thread_id: Optional[int]

    def __init__(self, workflow_ir: WorkflowIr) -> None:
        visibility = WorkflowVisibilityIndex.from_workflow_ir(workflow_ir)
        self._visible_by_consumer_node_id = visibility.visible_by_consumer_node_id
        self._values_by_producer_node_id = {}
        self._owner_thread_id = threading.current_thread().ident

    def _assert_owner_thread(self) -> None:
        if threading.current_thread().ident != self._owner_thread_id:
            msg = "WorkflowCtxStore write must be called from controller thread"
            raise RuntimeError(msg)

    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]:
        return self._visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())

    def publish_default_summary(self, producer_node_id: str, result: ExecutionResult) -> None:
        self._assert_owner_thread()
        node_id = str(producer_node_id)
        self.publish(node_id, "output_path", result.output_path, path="$ctx")
        self.publish(node_id, "total_rows", int(result.total_rows), path="$ctx")
        self.publish(node_id, "duration_secs", float(result.duration), path="$ctx")

    def publish(self, producer_node_id: str, key: str, value: object, *, path: str) -> None:
        self._assert_owner_thread()
        node_id = str(producer_node_id)
        ctx_key = str(key)
        ctx_value = ensure_json_like(value, path=path)

        by_key = self._values_by_producer_node_id.setdefault(node_id, {})
        by_key[ctx_key] = ctx_value

    def resolve(self, consumer_node_id: str, *, node: str, key: str, path: str) -> object:
        consumer = str(consumer_node_id)
        producer = str(node)
        ctx_key = str(key)

        if producer == consumer:
            msg = "$ctx does not allow node=self (node_id={})".format(consumer)
            raise ScalimWorkflowConfigError(msg, path=path)

        visible = self.visible_producer_node_ids(consumer)
        if producer not in visible:
            msg = "ctx key '{}' from node '{}' is not visible to node '{}' (declare depends_on)".format(ctx_key, producer, consumer)
            raise ScalimWorkflowConfigError(msg, path=path)

        by_key = self._values_by_producer_node_id.get(producer) or {}
        if ctx_key not in by_key:
            msg = "Unknown ctx key '{}' for node '{}'".format(ctx_key, producer)
            raise ScalimWorkflowConfigError(msg, path=path)
        return by_key[ctx_key]


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def iter_ctx_directives(value: object, *, path: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if _is_dict(value):
        mapping = value
        if len(mapping) == 1 and "$ctx" in mapping:
            directive = mapping.get("$ctx")
            if not _is_dict(directive):
                msg = "$ctx directive must be a mapping"
                raise ScalimWorkflowConfigError(msg, path=path)
            node_raw = directive.get("node")
            key_raw = directive.get("key")
            node_id = str(node_raw or "").strip() if isinstance(node_raw, str) else ""
            ctx_key = str(key_raw or "").strip() if isinstance(key_raw, str) else ""
            if not node_id:
                msg = "$ctx.node must be a non-empty string"
                raise ScalimWorkflowConfigError(msg, path=path)
            if not ctx_key:
                msg = "$ctx.key must be a non-empty string"
                raise ScalimWorkflowConfigError(msg, path=path)
            out.append((node_id, ctx_key))
            return out
        for raw_key, raw_value in mapping.items():
            child_path = "{}.{}".format(path, str(raw_key))
            out.extend(iter_ctx_directives(raw_value, path=child_path))
        return out

    if _is_list(value):
        for idx, item in enumerate(value):
            child_path = "{}.{}".format(path, idx)
            out.extend(iter_ctx_directives(item, path=child_path))
    return out


def render_ctx_directives(value: object, *, consumer_node_id: str, ctx_store: WorkflowCtxStore, path: str) -> object:
    if _is_dict(value):
        mapping = value
        if len(mapping) == 1 and "$ctx" in mapping:
            directive = mapping.get("$ctx")
            if not _is_dict(directive):
                msg = "$ctx directive must be a mapping"
                raise ScalimWorkflowConfigError(msg, path=path)
            node_raw = directive.get("node")
            key_raw = directive.get("key")
            node_id = str(node_raw or "").strip() if isinstance(node_raw, str) else ""
            ctx_key = str(key_raw or "").strip() if isinstance(key_raw, str) else ""
            if not node_id:
                msg = "$ctx.node must be a non-empty string"
                raise ScalimWorkflowConfigError(msg, path=path)
            if not ctx_key:
                msg = "$ctx.key must be a non-empty string"
                raise ScalimWorkflowConfigError(msg, path=path)
            value = ctx_store.resolve(str(consumer_node_id), node=node_id, key=ctx_key, path=path)
            return ensure_json_like(value, path=path)

        out: Dict[object, object] = {}
        for raw_key, raw_value in mapping.items():
            child_path = "{}.{}".format(path, str(raw_key))
            out[raw_key] = render_ctx_directives(raw_value, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path=child_path)
        return out

    if _is_list(value):
        return [
            render_ctx_directives(item, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path="{}.{}".format(path, idx))
            for idx, item in enumerate(value)
        ]

    return value


def _render_workflow_init_vars(
    init_vars: Optional[Dict[str, object]],
    *,
    consumer_node_id: str,
    ctx_store: WorkflowCtxStore,
    path_prefix: str,
) -> Dict[str, object]:
    if init_vars is None:
        return {}
    out: Dict[str, object] = {}
    for key, value in init_vars.items():
        item_path = "{}.{}".format(path_prefix, key)
        rendered = render_ctx_directives(value, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path=item_path)
        out[str(key)] = ensure_json_like(rendered, path=item_path)
    return out


def _validate_workflow_ctx_refs(workflow_ir: WorkflowIr, *, ctx_store: WorkflowCtxStore) -> None:
    node_ids = {str(node.node_id) for node in workflow_ir.nodes}
    for node in workflow_ir.nodes:
        if not isinstance(node, WorkflowNodeIr):
            continue
        node_id = str(node.node_id)
        init_vars = node.init_vars
        if not init_vars:
            continue
        visible = ctx_store.visible_producer_node_ids(node_id)
        prefix = "workflow.runs.{}.init_vars".format(int(node.decl_order))
        for key, value in init_vars.items():
            item_path = "{}.{}".format(prefix, key)
            for ref_node_id, _ref_key in iter_ctx_directives(value, path=item_path):
                if ref_node_id == node_id:
                    msg = "$ctx does not allow node=self (node_id={})".format(node_id)
                    raise ScalimWorkflowConfigError(msg, path=item_path)
                if ref_node_id not in node_ids:
                    msg = "Unknown ctx node '{}'".format(ref_node_id)
                    raise ScalimWorkflowConfigError(msg, path=item_path)
                if ref_node_id not in visible:
                    msg = "ctx reference to node '{}' is not visible to node '{}' (declare depends_on)".format(ref_node_id, node_id)
                    raise ScalimWorkflowConfigError(msg, path=item_path)


class ScalimWorkflowRunFailedError(ScalimWorkflowError):
    run_id: str
    demand_path: str

    def __init__(self, message: str, *, run_id: str, demand_path: str) -> None:
        super(ScalimWorkflowRunFailedError, self).__init__(message)
        self.run_id = str(run_id)
        self.demand_path = str(demand_path)


@dataclass
class _PreparedWorkflowRun:
    workflow_path: str
    workflow_exec_id: str
    workflow_components: Tuple[object, ...]
    workflow_ir: WorkflowIr
    artifacts_dir: WorkflowArtifactsDirectory
    ctx_store: WorkflowCtxStore
    max_concurrency: int
    failure_policy: str
    workflow_wall_start_ts: float
    bundle_viz_base_config: Optional[VizObserverConfig]
    workflow_observer_manager: ObserverManager
    workflow_viz_observer: Optional[WorkflowVizObserver]
    workflow_instrumentation: InstrumentationHub
    workflow_cache_pool: Optional[WorkflowCachePool]
    resource_manager: WorkflowResourceManager
    resource_lifecycle: WorkflowResourceLifecycle
    write_output_ids_by_run_id: Dict[str, FrozenSet[str]]
    write_consumers_remaining_by_output_key: Dict[Tuple[str, str], int]
    main_rows_consumers_remaining_by_run_id: Dict[str, int]
    capture_observability: bool
    workflow_replay_instrumentation: Optional[InstrumentationHub]
    captured_demand_events_by_node_id: Dict[str, List[Event]]
    captured_demand_hook_events_by_node_id: Dict[str, List[HookRecordedEvent]]
    captured_demand_viz_observer_by_node_id: Dict[str, Optional[Observer]]
    captured_demand_request_by_node_id: Dict[str, object]


def _build_workflow_instrumentation(
    *,
    workflow_exec_id: str,
    workflow_path: str,
    workflow_ir: WorkflowIr,
    components: Optional[Sequence[object]],
    bundle_viz_base_config: Optional[VizObserverConfig],
) -> Tuple[ObserverManager, Optional[WorkflowVizObserver], InstrumentationHub]:
    # 工作流层事件:复用 `hooks`/`observers` 分发通道,并以 `workflow_exec_id` 作为 `run_id` 分区.
    component_observers, component_hooks = split_components(components)
    workflow_observer_manager = Observability().build_manager(run_id=workflow_exec_id)
    try:
        for observer in component_observers:
            workflow_observer_manager.register(observer)

        workflow_viz_observer: Optional[WorkflowVizObserver] = None
        if bundle_viz_base_config is not None:
            workflow_viz_config = replace(bundle_viz_base_config, run_id="workflow")
            workflow_snapshot = build_workflow_viz_graph_snapshot(
                workflow_ir,
                demand_run_id_by_workflow_node_id={},
                workflow_yaml_path=workflow_path,
            )
            workflow_viz_observer = WorkflowVizObserver(config=workflow_viz_config, snapshot=workflow_snapshot)
            workflow_observer_manager.register(workflow_viz_observer)

        workflow_hook_manager = HookManager()
        for hook in component_hooks:
            workflow_hook_manager.register(hook)

        workflow_instrumentation = InstrumentationHub(
            hook_manager=workflow_hook_manager,
            observer_manager=workflow_observer_manager,
        )
    except Exception:
        with contextlib.suppress(Exception):
            workflow_observer_manager.close()
        raise
    else:
        return workflow_observer_manager, workflow_viz_observer, workflow_instrumentation


def _maybe_build_workflow_cache_pool(
    *,
    workflow_exec_id: str,
    workflow_ir: WorkflowIr,
    workflow_instrumentation: InstrumentationHub,
    logical_keys_by_node_id: Optional[Dict[str, FrozenSet[Tuple[str, str]]]],
    consumers_by_logical_key: Optional[Dict[Tuple[str, str], FrozenSet[str]]],
) -> Optional[WorkflowCachePool]:
    cache_pool_ir = workflow_ir.options.cache_pool
    if cache_pool_ir is None:
        return None

    if logical_keys_by_node_id is None or consumers_by_logical_key is None:
        msg = "workflow cache_pool requires derived consumers mapping"
        raise ScalimWorkflowConfigError(msg, path="workflow_runtime_options.cache_pool")
    return WorkflowCachePool(
        workflow_exec_id=workflow_exec_id,
        instrumentation=workflow_instrumentation,
        config=cache_pool_ir,
        logical_keys_by_node_id=logical_keys_by_node_id,
        consumers_by_logical_key=consumers_by_logical_key,
    )


def _build_write_output_ids_by_run_id(workflow_ir: WorkflowIr) -> Dict[str, FrozenSet[str]]:
    tmp_write_output_ids: Dict[str, Set[str]] = {}
    for node in workflow_ir.nodes:
        if isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            tmp_write_output_ids.setdefault(str(node.input_node_id), set()).add(str(node.input_output_id))
    return {run_id: frozenset(sorted(ids)) for run_id, ids in tmp_write_output_ids.items()}


def _build_write_consumers_remaining_by_output_key(workflow_ir: WorkflowIr) -> Dict[Tuple[str, str], int]:
    counts: Dict[Tuple[str, str], int] = {}
    for node in workflow_ir.nodes:
        if isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            key = (str(node.input_node_id), str(node.input_output_id))
            counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _build_main_rows_consumers_remaining_by_run_id(workflow_ir: WorkflowIr) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for node in workflow_ir.nodes:
        if not isinstance(node, WorkflowNodeIr):
            continue
        producer_run_id = str(node.main_rows_from_run_id or "").strip()
        if not producer_run_id:
            continue
        counts[producer_run_id] = int(counts.get(producer_run_id, 0)) + 1
    return counts


def _prepare_workflow_run_ir(
    workflow_path: str,
    workflow_ir: WorkflowIr,
    *,
    components: Optional[Sequence[object]],
    bundle_viz_base_config: Optional[VizObserverConfig],
    cache_pool_logical_keys_by_node_id: Optional[Dict[str, FrozenSet[Tuple[str, str]]]],
    cache_pool_consumers_by_logical_key: Optional[Dict[Tuple[str, str], FrozenSet[str]]],
) -> _PreparedWorkflowRun:
    workflow_exec_id = generate_run_id(prefix="wf")
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)
    ctx_store = WorkflowCtxStore(workflow_ir)
    _validate_workflow_ctx_refs(workflow_ir, ctx_store=ctx_store)

    max_concurrency = int(workflow_ir.options.max_concurrency)
    failure_policy = normalize_failure_policy(workflow_ir.options.failure_policy, label="workflow.options.failure_policy")
    workflow_wall_start_ts = time.time()

    workflow_observer_manager: Optional[ObserverManager] = None
    workflow_cache_pool: Optional[WorkflowCachePool] = None
    try:
        workflow_observer_manager, workflow_viz_observer, workflow_instrumentation = _build_workflow_instrumentation(
            workflow_exec_id=workflow_exec_id,
            workflow_path=workflow_path,
            workflow_ir=workflow_ir,
            components=components,
            bundle_viz_base_config=bundle_viz_base_config,
        )

        component_observers, component_hooks = split_components(components)
        capture_observability = int(max_concurrency) > 1 and bool(component_observers or component_hooks)
        workflow_replay_instrumentation: Optional[InstrumentationHub] = None
        if capture_observability:
            workflow_replay_instrumentation = workflow_instrumentation
            capture_hook_manager = HookCaptureManager(workflow_instrumentation.hook_manager)
            capture_observer_manager = workflow_observer_manager.create_capture_manager()
            capture_hook_manager.loader_result_policy = normalize_loader_result_policy("summary")
            capture_observer_manager.loader_result_policy = normalize_loader_result_policy("summary")
            capture_observer_manager.max_recorded_events = None
            workflow_instrumentation = InstrumentationHub(
                hook_manager=capture_hook_manager,
                observer_manager=capture_observer_manager,
            )

        if workflow_viz_observer is not None:
            _ = workflow_instrumentation.emit(
                "workflow_started",
                {
                    "workflow_id": str(Path(workflow_path).name),
                    "workflow_exec_id": str(workflow_exec_id),
                    "max_concurrency": int(max_concurrency),
                },
            )
        workflow_cache_pool = _maybe_build_workflow_cache_pool(
            workflow_exec_id=workflow_exec_id,
            workflow_ir=workflow_ir,
            workflow_instrumentation=workflow_instrumentation,
            logical_keys_by_node_id=cache_pool_logical_keys_by_node_id,
            consumers_by_logical_key=cache_pool_consumers_by_logical_key,
        )
        (
            workbook_defs,
            workbook_allow_formulas_by_id,
            csv_defs,
            sheetbook_defs,
        ) = _build_workflow_resource_defs(workflow_ir, workflow_exec_id=str(workflow_exec_id))
        resource_manager = WorkflowResourceManager(
            workflow_exec_id=workflow_exec_id,
            instrumentation=workflow_instrumentation,
            workbook_defs=workbook_defs,
            workbook_allow_formulas=workbook_allow_formulas_by_id,
            csv_defs=csv_defs,
            sheetbook_defs=sheetbook_defs,
            output_staging_dir_name=str(workflow_ir.options.output_staging.dir_name),
            output_staging_keep_on_success=bool(workflow_ir.options.output_staging.keep_on_success),
            output_staging_keep_on_failure=bool(workflow_ir.options.output_staging.keep_on_failure),
        )
        resource_lifecycle = WorkflowResourceLifecycle(
            resource_manager=resource_manager,
            artifacts_dir=artifacts_dir,
            cache_pool=workflow_cache_pool,
        )
        write_output_ids_by_run_id = _build_write_output_ids_by_run_id(workflow_ir)
        write_consumers_remaining_by_output_key = _build_write_consumers_remaining_by_output_key(workflow_ir)
        main_rows_consumers_remaining_by_run_id = _build_main_rows_consumers_remaining_by_run_id(workflow_ir)

        return _PreparedWorkflowRun(
            workflow_path=workflow_path,
            workflow_exec_id=workflow_exec_id,
            workflow_components=tuple(components or ()),
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=ctx_store,
            max_concurrency=int(max_concurrency),
            failure_policy=failure_policy,
            workflow_wall_start_ts=float(workflow_wall_start_ts),
            bundle_viz_base_config=bundle_viz_base_config,
            workflow_observer_manager=workflow_observer_manager,
            workflow_viz_observer=workflow_viz_observer,
            workflow_instrumentation=workflow_instrumentation,
            workflow_cache_pool=workflow_cache_pool,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id=write_output_ids_by_run_id,
            write_consumers_remaining_by_output_key=write_consumers_remaining_by_output_key,
            main_rows_consumers_remaining_by_run_id=main_rows_consumers_remaining_by_run_id,
            capture_observability=bool(capture_observability),
            workflow_replay_instrumentation=workflow_replay_instrumentation,
            captured_demand_events_by_node_id={},
            captured_demand_hook_events_by_node_id={},
            captured_demand_viz_observer_by_node_id={},
            captured_demand_request_by_node_id={},
        )
    except Exception:
        if workflow_cache_pool is not None:
            with contextlib.suppress(Exception):
                workflow_cache_pool.close()
        if workflow_observer_manager is not None:
            with contextlib.suppress(Exception):
                workflow_observer_manager.close()
        raise


def _compile_demand_node(
    node: WorkflowNodeIr,
    *,
    workflow_exec_id: str,
    ctx_store: WorkflowCtxStore,
    compile_demand_fn: Callable[..., object],
    bundle_viz_base_config: Optional[VizObserverConfig],
    write_output_ids_by_run_id: Dict[str, FrozenSet[str]],
    main_rows_consumers_remaining_by_run_id: Dict[str, int],
    artifacts_dir: WorkflowArtifactsDirectory,
) -> Tuple[object, ExecutionRequest]:
    node_id = str(node.node_id)
    demand_path = str(node.demand_path or "")

    node_init_vars = _render_workflow_init_vars(
        node.init_vars,
        consumer_node_id=node_id,
        ctx_store=ctx_store,
        path_prefix="workflow.runs.{}.init_vars".format(int(node.decl_order)),
    )

    managed_output_ids = write_output_ids_by_run_id.get(node_id)

    node_viz_config = None
    if bundle_viz_base_config is not None:
        node_viz_config = replace(bundle_viz_base_config, run_id=str(node_id))

    compilation = compile_demand_fn(
        demand_path,
        workflow_exec_id=str(workflow_exec_id),
        workflow_node_id=str(node_id),
        workflow_node_decl_order=int(node.decl_order),
        node_init_vars=node_init_vars,
        managed_output_ids=managed_output_ids,
        viz_config=node_viz_config,
    )
    comp = cast("_CompilationLike", compilation)  # pragma: allow-cast compile_demand typed narrowing
    base_request = cast("ExecutionRequest", comp.request)  # pragma: allow-cast compilation.request narrow
    overrides = WorkflowNodeRequestOverrides()
    if node_id in main_rows_consumers_remaining_by_run_id:
        overrides = replace(overrides, capture_in_memory_rows=True)

    producer_run_id = str(node.main_rows_from_run_id or "").strip()
    if producer_run_id:
        try:
            typed_rows_obj = artifacts_dir.get(str(node_id), producer_run_id, "in_memory_rows")
        except ValueError as exc:
            path = "workflow.runs.{}.main_rows_from_run_id".format(int(node.decl_order))
            raise ScalimWorkflowConfigError(str(exc), path=path) from exc
        if not isinstance(typed_rows_obj, InMemoryRows):
            msg = "Missing workflow-managed typed rows artifact: producer_node_id={!r}".format(producer_run_id)
            raise ScalimWorkflowWriteError(msg)
        overrides = replace(overrides, main_rows=iter_in_memory_rows_as_main_rows(typed_rows_obj))

    request_for_run = merge_workflow_node_request(base_request, overrides)
    return compilation, request_for_run


def _execute_workflow_run(
    prepared: _PreparedWorkflowRun,
    *,
    compile_demand_fn: Callable[..., object],
    build_demand_run_result_fn: Optional[Callable[..., object]],
    run_ir_fn: Callable[..., ExecutionResult],
) -> Tuple[List[WorkflowRunOutcome], Optional[WorkflowRunOutcome], Optional[BaseException]]:
    max_concurrency = int(prepared.max_concurrency)
    failure_policy = normalize_failure_policy(prepared.failure_policy, label="workflow.options.failure_policy")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        controller = WorkflowRunController.build_for_prepared_run(
            executor=executor,
            workflow_exec_id=str(prepared.workflow_exec_id),
            workflow_ir=prepared.workflow_ir,
            artifacts_dir=prepared.artifacts_dir,
            ctx_store=prepared.ctx_store,
            max_concurrency=int(max_concurrency),
            failure_policy=failure_policy,
            bundle_viz_base_config=prepared.bundle_viz_base_config,
            workflow_instrumentation=prepared.workflow_instrumentation,
            workflow_cache_pool=prepared.workflow_cache_pool,
            resource_manager=prepared.resource_manager,
            resource_lifecycle=prepared.resource_lifecycle,
            write_output_ids_by_run_id=prepared.write_output_ids_by_run_id,
            write_consumers_remaining_by_output_key=prepared.write_consumers_remaining_by_output_key,
            main_rows_consumers_remaining_by_run_id=prepared.main_rows_consumers_remaining_by_run_id,
            captured_demand_events_by_node_id=prepared.captured_demand_events_by_node_id,
            captured_demand_hook_events_by_node_id=prepared.captured_demand_hook_events_by_node_id,
            captured_demand_viz_observer_by_node_id=prepared.captured_demand_viz_observer_by_node_id,
            captured_demand_request_by_node_id=prepared.captured_demand_request_by_node_id,
            compile_demand_node_fn=_compile_demand_node,
            compile_demand_fn=compile_demand_fn,
            build_demand_run_result_fn=build_demand_run_result_fn,
            run_ir_fn=run_ir_fn,
            run_workflow_write_node_fn=_run_workflow_write_node,
            capture_observability=bool(prepared.capture_observability),
            workflow_replay_instrumentation=prepared.workflow_replay_instrumentation,
            workflow_components=prepared.workflow_components,
        )
        controller.run()
        return controller.finalize()


def _report_workflow_viz_finished(prepared: _PreparedWorkflowRun) -> None:
    if prepared.workflow_viz_observer is None or prepared.bundle_viz_base_config is None:
        return

    total_duration_ms = int(max(0.0, time.time() - prepared.workflow_wall_start_ts) * 1000)
    status = "error" if sys.exc_info()[1] is not None else "ok"
    with contextlib.suppress(Exception):
        _ = prepared.workflow_instrumentation.emit(
            "workflow_finished",
            {
                "workflow_id": str(Path(prepared.workflow_path).name),
                "workflow_exec_id": str(prepared.workflow_exec_id),
                "status": status,
                "total_duration_ms": total_duration_ms,
            },
        )

    # 子运行完成后重写工作流快照,避免生成指向缺失子运行的下钻链接.
    with contextlib.suppress(Exception):
        reporter = WorkflowVizReporter(
            prepared.workflow_ir,
            workflow_yaml_path=prepared.workflow_path,
            base_config=prepared.bundle_viz_base_config,
        )
        replays: List[str] = []
        for node in prepared.workflow_ir.nodes:
            if not isinstance(node, WorkflowNodeIr):
                continue
            node_id = str(node.node_id or "").strip()
            if not node_id:
                continue  # pragma: no cover  # pragma: allow-no-cover unreachable: node_id required by IR
            replays.append(node_id)
        reporter.fix_child_replay_links(replays, parent_run_id="workflow")


def _replay_captured_workflow_observability(prepared: _PreparedWorkflowRun) -> None:
    WorkflowRunController.replay_captured_observability(
        capture_observability=bool(prepared.capture_observability),
        workflow_replay_instrumentation=prepared.workflow_replay_instrumentation,
        workflow_instrumentation=prepared.workflow_instrumentation,
        workflow_ir=prepared.workflow_ir,
        workflow_exec_id=str(prepared.workflow_exec_id),
        workflow_components=prepared.workflow_components,
        captured_demand_events_by_node_id=prepared.captured_demand_events_by_node_id,
        captured_demand_hook_events_by_node_id=prepared.captured_demand_hook_events_by_node_id,
        captured_demand_viz_observer_by_node_id=prepared.captured_demand_viz_observer_by_node_id,
        captured_demand_request_by_node_id=prepared.captured_demand_request_by_node_id,
    )


def _cleanup_workflow_finally(prepared: _PreparedWorkflowRun, *, resources_finalized: bool) -> None:
    prepared.resource_lifecycle.cleanup_finally(resources_finalized=bool(resources_finalized))
    with contextlib.suppress(Exception):
        cast("Any", prepared.workflow_observer_manager).close()  # pragma: allow-cast observer manager close boundary


def run_workflow_ir(
    workflow_path: str,
    workflow_ir: WorkflowIr,
    *,
    compile_demand_fn: Callable[..., object],
    build_demand_run_result_fn: Optional[Callable[..., object]] = None,
    run_ir_fn: Optional[Callable[..., ExecutionResult]] = None,
    components: Optional[Sequence[object]] = None,
    bundle_viz_base_config: Optional[VizObserverConfig] = None,
    cache_pool_logical_keys_by_node_id: Optional[Dict[str, FrozenSet[Tuple[str, str]]]] = None,
    cache_pool_consumers_by_logical_key: Optional[Dict[Tuple[str, str], FrozenSet[str]]] = None,
) -> WorkflowResult:
    prepared: Optional[_PreparedWorkflowRun] = None
    resources_finalized = False
    try:
        prepared = _prepare_workflow_run_ir(
            workflow_path,
            workflow_ir,
            components=components,
            bundle_viz_base_config=bundle_viz_base_config,
            cache_pool_logical_keys_by_node_id=cache_pool_logical_keys_by_node_id,
            cache_pool_consumers_by_logical_key=cache_pool_consumers_by_logical_key,
        )
        final_outcomes, failed, failed_exc = _execute_workflow_run(
            prepared,
            compile_demand_fn=compile_demand_fn,
            build_demand_run_result_fn=build_demand_run_result_fn,
            run_ir_fn=run_ir_fn or run_ir,
        )
        try:
            has_errors = any(o.error is not None for o in final_outcomes)
            discard_node_id = failed.run_id if failed is not None else "__wf__discard"
            prepared.resource_lifecycle.commit_or_discard(
                success=not has_errors,
                discard_node_id=str(discard_node_id),
            )
            resources_finalized = True
        except ScalimWorkflowConfigError:
            resources_finalized = True
            raise

        result = WorkflowResult(outcomes=tuple(final_outcomes))
        if failed is not None and prepared.failure_policy == FailurePolicy.ALL_FAIL:
            msg = "工作流运行失败(run_id={}, demand_path={})".format(failed.run_id, failed.demand_path)
            exc = ScalimWorkflowRunFailedError(msg, run_id=failed.run_id, demand_path=failed.demand_path)
            if failed_exc is not None:
                exc.__cause__ = failed_exc
            raise exc
        return result
    finally:
        if prepared is not None:
            _report_workflow_viz_finished(prepared)
            with contextlib.suppress(Exception):
                _replay_captured_workflow_observability(prepared)
            _cleanup_workflow_finally(prepared, resources_finalized=resources_finalized)


__all__ = (
    "ScalimWorkflowRunFailedError",
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunOutcome",
    "run_workflow_ir",
)
