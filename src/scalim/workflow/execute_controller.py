# pragma: allow-c901-file plan: c90
import concurrent.futures
import contextlib
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple, Union, cast

from .._internal.loggingx import format_kv, get_logger
from .._internal.loggingx import prefix as log_prefix
from ..events import (
    Event,
    EventType,
    WorkflowNodeCancelledReason,
    WorkflowNodeEndStatus,
)
from ..events._events import (
    WorkflowNodeCancelledEvent,
    WorkflowNodeEndEvent,
    WorkflowNodeStartEvent,
    WorkflowResourceCommitEvent,
)
from ..execution.adaptive.capture import HookRecordedEvent
from ..execution.engine import ScalimEngine
from ..execution.run_ir import ExecutionRequest, ExecutionResult, run_ir, run_ir_capture_events
from ..execution.workflow_cache_pool import ScalimWorkflowCachePoolError, WorkflowCachePool
from ..hooks import HookManager
from ..ob.components import split_components
from ..ob.hub import InstrumentationHub
from ..ob.observability import Observability, ObservabilityOptions
from ..ob.observer import Observer
from ..ob.presets.viz import VizObserverConfig
from ..spec.ir import DemandIr
from ..spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WriteSheetNodeIr,
)
from ..typedefs import FailurePolicy, parse_failure_policy
from ..vendor.compact.typing_extensionsx import Protocol
from ..vendor.dataclassesx import dataclass, field
from ._internal.replay_event_classification import (
    classify_workflow_events_for_replay as _classify_workflow_events_for_replay,
)
from .artifacts import WorkflowArtifactsDirectory
from .errors import ScalimWorkflowConfigError
from .loaders import workflow_loader_context
from .outcome_builder import build_outcome_from_exception, build_outcome_from_result, safe_error_message, safe_error_type
from .report import WorkflowRunError, WorkflowRunOutcome
from .resource_lifecycle import WorkflowResourceLifecycle
from .resources import WorkflowResourceManager
from .scheduler_rules import can_schedule_more, should_cancel_on_failure
from .stage_attribution import derive_workflow_struct_levels, derive_workflow_user_stages

_ERR_WRITE_NODE_SCHEDULED_WHILE_FUTURES_IN_FLIGHT = "write node must not be scheduled while demand futures are in-flight"


class _WorkflowCtxStoreLike(Protocol):
    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]: ...

    def publish_default_summary(self, producer_node_id: str, result: ExecutionResult) -> None: ...


@dataclass(frozen=True)
class _CapturedNodeRun:
    core: ExecutionResult
    captured_hook_events: List[HookRecordedEvent]
    captured_events: List[Event]
    viz_observer: Optional[Observer]


@dataclass
class WorkflowRunState:
    """工作流执行状态(阶段 0).

    说明:
    - 该数据类用于收拢原先散落在闭包/多个映射中的隐式状态.
    - 阶段 0 以“搬迁不改逻辑”为目标,因此字段与旧实现保持较强的一一对应关系.
    """

    outcomes: List[Optional[WorkflowRunOutcome]]
    node_state: Dict[str, str]
    ready_queue: List[str]
    submitted: Dict[
        "concurrent.futures.Future[Any]",
        Tuple[str, WorkflowAnyNodeIr, Optional[str], Optional[Any], Optional[ExecutionRequest]],
    ]
    remaining_prereqs: Dict[str, int]
    prereq_failed: Dict[str, bool]
    max_concurrency: int
    failure_policy: str

    failed_outcome: Optional[WorkflowRunOutcome] = None
    failed_exc: Optional[BaseException] = None

    write_consumers_remaining_by_output_key: Dict[Tuple[str, str], int] = field(default_factory=dict)
    main_rows_consumers_remaining_by_run_id: Dict[str, int] = field(default_factory=dict)

    captured_demand_events_by_node_id: Dict[str, List[Event]] = field(default_factory=dict)
    captured_demand_hook_events_by_node_id: Dict[str, List[HookRecordedEvent]] = field(default_factory=dict)
    captured_demand_viz_observer_by_node_id: Dict[str, Optional[Observer]] = field(default_factory=dict)
    captured_demand_request_by_node_id: Dict[str, ExecutionRequest] = field(default_factory=dict)


def _build_demand_replay_instrumentation(  # noqa: C901
    request: Optional[ExecutionRequest],
    viz_observer: Optional[Observer],
    *,
    workflow_components: Tuple[Any, ...],
) -> Optional[InstrumentationHub]:
    if request is None and viz_observer is None:
        return None

    fallback_logger_enabled = False
    components: List[Any] = []
    if request is not None:
        req = request
        obs_spec = req.observability
        if obs_spec is not None:
            fallback_logger_enabled = bool(obs_spec.fallback_logger_enabled)
        req_components = req.components
        if req_components:
            workflow_component_ids = {id(c) for c in workflow_components}
            for component in list(req_components):
                if id(component) in workflow_component_ids:
                    continue
                components.append(component)

    observers, hooks = split_components(components)
    if viz_observer is None and not observers and not hooks:
        return None

    observer_manager = Observability(options=ObservabilityOptions(fallback_logger_enabled=fallback_logger_enabled)).build_manager()
    for observer in observers:
        observer_manager.register(observer)
    if viz_observer is not None:
        observer_manager.register(viz_observer)

    hook_manager = HookManager(fallback_logger_enabled=fallback_logger_enabled)
    for hook in hooks:
        hook_manager.register(hook)

    return InstrumentationHub(hook_manager=hook_manager, observer_manager=observer_manager)


class WorkflowRunController:
    """工作流执行控制器(阶段 0).

    说明:
    - 阶段 0 目标: 引入显式 `State`/`Controller`,并把旧实现逻辑搬迁进来(尽量不改行为).
    - 依赖通过构造参数注入,减少隐式耦合,方便单测对拍.
    """

    _executor: concurrent.futures.ThreadPoolExecutor
    _state: WorkflowRunState

    _workflow_exec_id: str
    _workflow_ir: WorkflowIr
    _artifacts_dir: WorkflowArtifactsDirectory
    _ctx_store: _WorkflowCtxStoreLike

    _bundle_viz_base_config: Optional[VizObserverConfig]
    _workflow_instrumentation: InstrumentationHub
    _workflow_cache_pool: Optional[WorkflowCachePool]
    _resource_manager: WorkflowResourceManager
    _resource_lifecycle: WorkflowResourceLifecycle
    _write_output_ids_by_run_id: Dict[str, FrozenSet[str]]

    _compile_demand_node: Callable[..., Tuple[Any, ExecutionRequest]]
    _compile_demand_fn: Callable[..., Any]
    _build_demand_run_result_fn: Optional[Callable[..., Any]]
    _run_ir_fn: Callable[..., ExecutionResult]
    _run_workflow_write_node: Callable[..., None]

    _capture_observability: bool
    _workflow_replay_instrumentation: Optional[InstrumentationHub]
    _workflow_components: Tuple[Any, ...]

    _node_by_id: Dict[str, WorkflowAnyNodeIr]
    _index_by_node_id: Dict[str, int]
    _dependents_by_node_id: Dict[str, List[str]]

    _schedule_mode: str
    _stage_by_node_id: Dict[str, int]
    _stage_order: List[int]
    _current_stage_idx: int
    _node_ids_by_stage: Dict[int, FrozenSet[str]]

    def __init__(  # noqa: PLR0913
        self,
        *,
        executor: concurrent.futures.ThreadPoolExecutor,
        state: WorkflowRunState,
        workflow_exec_id: str,
        workflow_ir: WorkflowIr,
        artifacts_dir: WorkflowArtifactsDirectory,
        ctx_store: _WorkflowCtxStoreLike,
        bundle_viz_base_config: Optional[VizObserverConfig],
        workflow_instrumentation: InstrumentationHub,
        workflow_cache_pool: Optional[WorkflowCachePool],
        resource_manager: WorkflowResourceManager,
        resource_lifecycle: WorkflowResourceLifecycle,
        write_output_ids_by_run_id: Dict[str, FrozenSet[str]],
        compile_demand_node_fn: Callable[..., Tuple[Any, ExecutionRequest]],
        compile_demand_fn: Callable[..., Any],
        build_demand_run_result_fn: Optional[Callable[..., Any]],
        run_ir_fn: Callable[..., ExecutionResult],
        run_workflow_write_node_fn: Callable[..., None],
        capture_observability: bool,
        workflow_replay_instrumentation: Optional[InstrumentationHub],
        workflow_components: Tuple[Any, ...],
    ) -> None:
        self._executor = executor
        self._state = state

        self._workflow_exec_id = str(workflow_exec_id)
        self._workflow_ir = workflow_ir
        self._artifacts_dir = artifacts_dir
        self._ctx_store = ctx_store

        self._bundle_viz_base_config = bundle_viz_base_config
        self._workflow_instrumentation = workflow_instrumentation
        self._workflow_cache_pool = workflow_cache_pool
        self._resource_manager = resource_manager
        self._resource_lifecycle = resource_lifecycle
        self._write_output_ids_by_run_id = write_output_ids_by_run_id

        self._compile_demand_node = compile_demand_node_fn
        self._compile_demand_fn = compile_demand_fn
        self._build_demand_run_result_fn = build_demand_run_result_fn
        self._run_ir_fn = run_ir_fn
        self._run_workflow_write_node = run_workflow_write_node_fn

        self._capture_observability = bool(capture_observability)
        self._workflow_replay_instrumentation = workflow_replay_instrumentation
        self._workflow_components = workflow_components

        self._node_by_id = {node.node_id: node for node in workflow_ir.nodes}
        self._index_by_node_id = {node.node_id: int(node.decl_order) for node in workflow_ir.nodes}
        self._dependents_by_node_id = {}
        for node in workflow_ir.nodes:
            for dep_id in node.deps:
                self._dependents_by_node_id.setdefault(str(dep_id), []).append(node.node_id)
        for children in self._dependents_by_node_id.values():
            children.sort(key=lambda nid: self._index_by_node_id.get(str(nid), 0))

        schedule_mode = str(workflow_ir.options.schedule_mode or "pipeline").strip() or "pipeline"
        self._schedule_mode = schedule_mode

        struct_levels = derive_workflow_struct_levels(workflow_ir)
        stage_by_node_id = derive_workflow_user_stages(workflow_ir, struct_levels=struct_levels)
        self._stage_by_node_id = stage_by_node_id

        tmp_stage_nodes: Dict[int, Set[str]] = {}
        for node in workflow_ir.nodes:
            node_id = str(node.node_id or "").strip()
            if not node_id:
                continue
            stage = int(stage_by_node_id.get(node_id, 0))
            tmp_stage_nodes.setdefault(int(stage), set()).add(str(node_id))
        self._node_ids_by_stage = {int(stage): frozenset(sorted(ids)) for stage, ids in tmp_stage_nodes.items()}
        self._stage_order = sorted(self._node_ids_by_stage.keys())
        self._current_stage_idx = 0

    @classmethod
    def build_for_prepared_run(  # noqa: PLR0913
        cls,
        *,
        executor: concurrent.futures.ThreadPoolExecutor,
        workflow_exec_id: str,
        workflow_ir: WorkflowIr,
        artifacts_dir: WorkflowArtifactsDirectory,
        ctx_store: _WorkflowCtxStoreLike,
        max_concurrency: int,
        failure_policy: str,
        bundle_viz_base_config: Optional[VizObserverConfig],
        workflow_instrumentation: InstrumentationHub,
        workflow_cache_pool: Optional[WorkflowCachePool],
        resource_manager: WorkflowResourceManager,
        resource_lifecycle: WorkflowResourceLifecycle,
        write_output_ids_by_run_id: Dict[str, FrozenSet[str]],
        write_consumers_remaining_by_output_key: Dict[Tuple[str, str], int],
        main_rows_consumers_remaining_by_run_id: Dict[str, int],
        captured_demand_events_by_node_id: Dict[str, List[Event]],
        captured_demand_hook_events_by_node_id: Dict[str, List[HookRecordedEvent]],
        captured_demand_viz_observer_by_node_id: Dict[str, Optional[Observer]],
        captured_demand_request_by_node_id: Dict[str, ExecutionRequest],
        compile_demand_node_fn: Callable[..., Tuple[Any, ExecutionRequest]],
        compile_demand_fn: Callable[..., Any],
        build_demand_run_result_fn: Optional[Callable[..., Any]],
        run_ir_fn: Callable[..., ExecutionResult],
        run_workflow_write_node_fn: Callable[..., None],
        capture_observability: bool,
        workflow_replay_instrumentation: Optional[InstrumentationHub],
        workflow_components: Tuple[Any, ...],
    ) -> "WorkflowRunController":
        outcomes: List[Optional[WorkflowRunOutcome]] = [None for _ in range(len(workflow_ir.nodes))]

        node_state: Dict[str, str] = {node.node_id: "pending" for node in workflow_ir.nodes}
        remaining_prereqs: Dict[str, int] = {node.node_id: len(node.deps) for node in workflow_ir.nodes}
        prereq_failed: Dict[str, bool] = {node.node_id: False for node in workflow_ir.nodes}

        ready_queue: List[str] = []
        index_by_node_id: Dict[str, int] = {node.node_id: int(node.decl_order) for node in workflow_ir.nodes}
        for node in workflow_ir.nodes:
            if remaining_prereqs.get(node.node_id, 0) == 0:
                node_state[node.node_id] = "ready"
                ready_queue.append(node.node_id)
        ready_queue.sort(key=lambda nid: index_by_node_id.get(str(nid), 0))

        state = WorkflowRunState(
            outcomes=outcomes,
            node_state=node_state,
            ready_queue=ready_queue,
            submitted={},
            remaining_prereqs=remaining_prereqs,
            prereq_failed=prereq_failed,
            max_concurrency=int(max_concurrency),
            failure_policy=parse_failure_policy(
                failure_policy,
                label="workflow_runtime_options.execution.failure_policy",
            ),
            write_consumers_remaining_by_output_key=write_consumers_remaining_by_output_key,
            main_rows_consumers_remaining_by_run_id=main_rows_consumers_remaining_by_run_id,
            captured_demand_events_by_node_id=captured_demand_events_by_node_id,
            captured_demand_hook_events_by_node_id=captured_demand_hook_events_by_node_id,
            captured_demand_viz_observer_by_node_id=captured_demand_viz_observer_by_node_id,
            captured_demand_request_by_node_id=captured_demand_request_by_node_id,
        )
        return cls(
            executor=executor,
            state=state,
            workflow_exec_id=str(workflow_exec_id),
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=ctx_store,
            bundle_viz_base_config=bundle_viz_base_config,
            workflow_instrumentation=workflow_instrumentation,
            workflow_cache_pool=workflow_cache_pool,
            resource_manager=resource_manager,
            resource_lifecycle=resource_lifecycle,
            write_output_ids_by_run_id=write_output_ids_by_run_id,
            compile_demand_node_fn=compile_demand_node_fn,
            compile_demand_fn=compile_demand_fn,
            build_demand_run_result_fn=build_demand_run_result_fn,
            run_ir_fn=run_ir_fn,
            run_workflow_write_node_fn=run_workflow_write_node_fn,
            capture_observability=bool(capture_observability),
            workflow_replay_instrumentation=workflow_replay_instrumentation,
            workflow_components=workflow_components,
        )

    @property
    def state(self) -> WorkflowRunState:
        return self._state

    def run(self) -> None:
        self.submit_ready_nodes()
        while self._state.submitted:
            done, _pending = concurrent.futures.wait(self._state.submitted.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                self.process_completed_future(fut)
            self.submit_ready_nodes()

    def _current_stage(self) -> int:
        if not self._stage_order:
            return 0
        idx = int(self._current_stage_idx)
        if idx < 0:
            return int(self._stage_order[0])
        if idx >= len(self._stage_order):
            return int(self._stage_order[-1])
        return int(self._stage_order[idx])

    def _maybe_advance_stage_barrier(self) -> None:
        if str(self._schedule_mode) != "stage_barrier":
            return
        terminal = {"done", "failed", "cancelled"}
        while True:
            if not self._stage_order:
                return
            stage = self._current_stage()
            members = self._node_ids_by_stage.get(int(stage), frozenset())
            if not members:
                if self._current_stage_idx + 1 >= len(self._stage_order):
                    return
                self._current_stage_idx += 1
                continue

            all_terminal = True
            for node_id in members:
                if self._state.node_state.get(str(node_id)) not in terminal:
                    all_terminal = False
                    break
            if not all_terminal:
                return

            if self._current_stage_idx + 1 >= len(self._stage_order):
                return
            self._current_stage_idx += 1

    def submit_ready_nodes(self) -> None:
        while True:
            self._maybe_advance_stage_barrier()
            if not self._state.ready_queue:
                return
            if should_cancel_on_failure(self._state.failure_policy, self._state.failed_outcome):
                return

            # 单写者模型: `write node` 在 `controller` 线程同步执行,
            # 且不会与 `in-flight` 的 `demand future` 重叠; 共享状态更新被约束在 `controller` 内,
            # 从而不再依赖 `artifacts/ctx/resources` 的线程锁。
            if self._state.submitted:
                if not can_schedule_more(len(self._state.submitted), self._state.max_concurrency):
                    return
                node_id = self._pop_next_ready_demand_node_id()
                if node_id is None:
                    return
                self._submit_one_ready_node(str(node_id))
                continue

            write_node_id = self._pop_next_ready_write_node_id()
            if write_node_id is not None:
                self._submit_one_ready_node(str(write_node_id))
                continue

            if not can_schedule_more(len(self._state.submitted), self._state.max_concurrency):
                return
            node_id = self._pop_next_ready_demand_node_id()
            if node_id is None:
                return
            self._submit_one_ready_node(str(node_id))

    def _pop_next_ready_demand_node_id(self) -> Optional[str]:
        for idx, node_id in enumerate(list(self._state.ready_queue)):
            node = self._node_by_id.get(str(node_id))
            if isinstance(node, WorkflowNodeIr):
                if self._schedule_mode == "stage_barrier" and int(self._stage_by_node_id.get(str(node_id), 0)) != self._current_stage():
                    continue
                return str(self._state.ready_queue.pop(int(idx)))
        return None

    def _pop_next_ready_write_node_id(self) -> Optional[str]:
        for idx, node_id in enumerate(list(self._state.ready_queue)):
            node = self._node_by_id.get(str(node_id))
            if node is not None and not isinstance(node, WorkflowNodeIr):
                if self._schedule_mode == "stage_barrier" and int(self._stage_by_node_id.get(str(node_id), 0)) != self._current_stage():
                    continue
                return str(self._state.ready_queue.pop(int(idx)))
        return None

    def _submit_one_ready_node(self, node_id: str) -> None:
        node = self._node_by_id[str(node_id)]
        self._state.node_state[str(node_id)] = "running"
        self._emit_workflow_node_start(node)

        if isinstance(node, WorkflowNodeIr):
            self._submit_demand_node(str(node_id), node)
            return

        if self._state.submitted:
            # pragma: allow-no-cover invariant: write nodes scheduled only after demand futures complete
            raise RuntimeError(_ERR_WRITE_NODE_SCHEDULED_WHILE_FUTURES_IN_FLIGHT)  # pragma: no cover
        idx = int(self._index_by_node_id.get(str(node_id), 0))
        try:
            self._run_workflow_write_node(
                node,
                artifacts_dir=self._artifacts_dir,
                resource_manager=self._resource_manager,
            )
            self._maybe_release_workflow_managed_in_memory_output(node)
            self._state.outcomes[idx] = WorkflowRunOutcome(run_id=str(node_id), demand_path="", result=None, error=None)
            self._maybe_release_workflow_main_rows_artifact(node)
            self._state.node_state[str(node_id)] = "done"
            self._emit_workflow_node_end(node, status=WorkflowNodeEndStatus.OK, exc=None)
            self._resource_lifecycle.on_node_terminal(str(node_id), ok=True)
            self._on_terminal(str(node_id), ok=True)
        except Exception as exc:  # noqa: BLE001
            self._mark_node_failed(node_id=str(node_id), node=node, demand_path="", exc=exc, idx=idx)

    def _submit_demand_node(self, node_id: str, node: WorkflowNodeIr) -> None:
        demand_path = str(node.demand_path or "")
        try:
            compilation, request_for_run = self._compile_demand_node(
                node,
                workflow_exec_id=str(self._workflow_exec_id),
                ctx_store=self._ctx_store,
                compile_demand_fn=self._compile_demand_fn,
                bundle_viz_base_config=self._bundle_viz_base_config,
                write_output_ids_by_run_id=self._write_output_ids_by_run_id,
                main_rows_consumers_remaining_by_run_id=self._state.main_rows_consumers_remaining_by_run_id,
                artifacts_dir=self._artifacts_dir,
            )
        except ScalimWorkflowConfigError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._mark_node_failed(
                node_id=str(node_id),
                node=node,
                demand_path=str(demand_path),
                exc=exc,
            )
            return

        demand_ir = cast("DemandIr", compilation.demand_ir)  # pragma: allow-cast compilation.demand_ir narrow
        visible = self._ctx_store.visible_producer_node_ids(str(node_id))
        fut = self._executor.submit(self._run_one, demand_ir, request_for_run, str(node_id), visible, str(demand_path))
        self._state.submitted[fut] = (str(node_id), node, str(demand_path), compilation, request_for_run)

    def process_completed_future(self, fut: "concurrent.futures.Future[Any]") -> None:
        node_id, node, demand_path, compilation, request = self._state.submitted.pop(fut)
        idx = int(self._index_by_node_id.get(str(node_id), 0))
        try:
            result_obj = fut.result()

            capture_obj = None
            if isinstance(result_obj, _CapturedNodeRun):
                capture_obj = result_obj
                result_obj = capture_obj.core

            if isinstance(node, WorkflowNodeIr):
                core = cast("ExecutionResult", result_obj)  # pragma: allow-cast future result typed narrowing
                if capture_obj is not None:
                    self._state.captured_demand_events_by_node_id[str(node_id)] = list(capture_obj.captured_events)
                    self._state.captured_demand_hook_events_by_node_id[str(node_id)] = list(capture_obj.captured_hook_events)
                    self._state.captured_demand_viz_observer_by_node_id[str(node_id)] = capture_obj.viz_observer
                    if request is not None:
                        self._state.captured_demand_request_by_node_id[str(node_id)] = request

                demand_yaml_path = str(demand_path or "")
                self._artifacts_dir.publish(str(node_id), "output_path", core.output_path)
                self._artifacts_dir.publish(str(node_id), "outputs", core.outputs)
                self._artifacts_dir.publish(str(node_id), "in_memory_csv_outputs", core.in_memory_csv_outputs or {})
                self._artifacts_dir.publish(str(node_id), "in_memory_rows_outputs", core.in_memory_rows_outputs or {})
                self._artifacts_dir.publish(
                    str(node_id),
                    "in_memory_csv_export_headers",
                    core.workflow_managed_output_export_headers or {},
                )
                if core.in_memory_rows is not None:
                    self._artifacts_dir.publish(str(node_id), "in_memory_rows", core.in_memory_rows)
                self._ctx_store.publish_default_summary(str(node_id), core)
                node_result: Any
                if self._build_demand_run_result_fn is None:
                    node_result = core
                else:
                    node_result = self._build_demand_run_result_fn(
                        core,
                        compilation=compilation,
                        demand_yaml_path=demand_yaml_path,
                        workflow_exec_id=str(self._workflow_exec_id),
                        workflow_node_id=str(node_id),
                    )
                self._state.outcomes[idx] = build_outcome_from_result(
                    node_result,
                    run_id=str(node_id),
                    demand_path=demand_yaml_path,
                )
            else:
                self._maybe_release_workflow_managed_in_memory_output(node)
                self._state.outcomes[idx] = build_outcome_from_result(None, run_id=str(node_id), demand_path="")

            self._maybe_release_workflow_main_rows_artifact(node)
            self._state.node_state[str(node_id)] = "done"
            self._emit_workflow_node_end(node, status=WorkflowNodeEndStatus.OK, exc=None)
            self._resource_lifecycle.on_node_terminal(str(node_id), ok=True)
            self._on_terminal(str(node_id), ok=True)
        except Exception as exc:
            if isinstance(exc, ScalimWorkflowCachePoolError):
                raise ScalimWorkflowConfigError(str(exc), path=exc.path) from exc
            self._mark_node_failed(
                node_id=str(node_id),
                node=node,
                demand_path=str(demand_path or ""),
                exc=exc,
                idx=idx,
            )

    def _mark_node_failed(
        self,
        *,
        node_id: str,
        node: WorkflowAnyNodeIr,
        demand_path: str,
        exc: BaseException,
        idx: Optional[int] = None,
    ) -> None:
        idx = int(idx if idx is not None else self._index_by_node_id.get(str(node_id), 0))
        outcome = build_outcome_from_exception(exc, run_id=str(node_id), demand_path=str(demand_path))
        self._state.outcomes[idx] = outcome
        self._state.node_state[str(node_id)] = "failed"
        self._emit_workflow_node_end(node, status=WorkflowNodeEndStatus.ERROR, exc=exc)
        self._maybe_release_workflow_main_rows_artifact(node)
        self._resource_lifecycle.on_node_terminal(str(node_id), ok=False)
        self._on_terminal(str(node_id), ok=False)

        if self._state.failure_policy == FailurePolicy.ALL_FAIL and self._state.failed_outcome is None:
            self._state.failed_outcome = outcome
            self._state.failed_exc = exc
            self._cancel_all_not_started_due_to_all_fail()

    def finalize(self) -> Tuple[List[WorkflowRunOutcome], Optional[WorkflowRunOutcome], Optional[BaseException]]:
        final_outcomes: List[WorkflowRunOutcome] = []
        for idx, outcome in enumerate(self._state.outcomes):
            if outcome is None:  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
                node_id = str(self._workflow_ir.nodes[idx].node_id)  # pragma: no cover  # pragma: allow-no-cover unreachable
                demand_path = str(
                    self._node_demand_path(self._workflow_ir.nodes[idx]) or ""
                )  # pragma: no cover  # pragma: allow-no-cover unreachable
                missing = WorkflowRunOutcome(  # pragma: no cover  # pragma: allow-no-cover unreachable
                    run_id=node_id,
                    demand_path=demand_path,
                    result=None,
                    error=WorkflowRunError(run_id=node_id, demand_path=demand_path, exc_type="Unknown", message="Missing outcome"),
                )
                final_outcomes.append(missing)  # pragma: no cover  # pragma: allow-no-cover unreachable
                continue  # pragma: no cover  # pragma: allow-no-cover unreachable
            final_outcomes.append(outcome)
        return final_outcomes, self._state.failed_outcome, self._state.failed_exc

    @staticmethod
    def replay_captured_observability(  # noqa: C901, PLR0912, PLR0915
        *,
        capture_observability: bool,
        workflow_replay_instrumentation: Optional[InstrumentationHub],
        workflow_instrumentation: InstrumentationHub,
        workflow_ir: WorkflowIr,
        workflow_exec_id: str,
        workflow_components: Tuple[Any, ...],
        captured_demand_events_by_node_id: Dict[str, List[Event]],
        captured_demand_hook_events_by_node_id: Dict[str, List[HookRecordedEvent]],
        captured_demand_viz_observer_by_node_id: Dict[str, Optional[Observer]],
        captured_demand_request_by_node_id: Dict[str, ExecutionRequest],
    ) -> None:
        if not capture_observability:
            return
        replay = workflow_replay_instrumentation
        if replay is None:
            return

        capture = workflow_instrumentation
        workflow_hook_events: List[HookRecordedEvent] = []
        with contextlib.suppress(Exception):
            workflow_hook_events = cast("Any", capture.hook_manager).drain_events()  # pragma: allow-cast capture hook manager drain
        for event in workflow_hook_events:
            replay.hook_manager.emit_typed(str(event.event_type), event.payload)

        workflow_events: List[Event] = []
        with contextlib.suppress(Exception):
            workflow_events = cast("Any", capture.observer_manager).drain_events()  # pragma: allow-cast capture observer manager drain

        known_node_ids: Set[str] = {node.node_id for node in workflow_ir.nodes}
        buckets = _classify_workflow_events_for_replay(workflow_events, known_node_ids=known_node_ids)

        workflow_seq = 0

        def _emit_workflow_event(event: Event) -> None:
            nonlocal workflow_seq
            workflow_seq += 1
            meta = dict(event.meta) if event.meta else {}
            replay.emit_recorded_event(
                Event(
                    event_type=str(event.event_type),
                    timestamp=float(event.timestamp),
                    run_id=str(workflow_exec_id),
                    payload=event.payload,
                    meta=meta,
                    seq=int(workflow_seq),
                )
            )

        def _replay_demand_node(node_id: str) -> None:
            hook_events = captured_demand_hook_events_by_node_id.get(str(node_id), [])
            observer_events = captured_demand_events_by_node_id.get(str(node_id), [])
            if observer_events:
                observer_events = sorted(observer_events, key=lambda e: int(e.seq))

            viz_observer = captured_demand_viz_observer_by_node_id.get(str(node_id))
            request = captured_demand_request_by_node_id.get(str(node_id))
            node_replay = _build_demand_replay_instrumentation(
                request,
                viz_observer,
                workflow_components=workflow_components,
            )
            for event in hook_events:
                replay.hook_manager.emit_typed(str(event.event_type), event.payload)
                if node_replay is not None:
                    node_replay.hook_manager.emit_typed(str(event.event_type), event.payload)
            for event in observer_events:
                replay.emit_recorded_event(event)
                if node_replay is not None:
                    node_replay.emit_recorded_event(event)
            if node_replay is not None:
                with contextlib.suppress(Exception):
                    node_replay.observer_manager.close()

        for event in buckets.started_events:
            _emit_workflow_event(event)

        nodes_in_order = sorted(workflow_ir.nodes, key=lambda n: int(n.decl_order))
        for node in nodes_in_order:
            node_id = str(node.node_id)
            for event in buckets.node_start_events_by_node_id.get(node_id, []):
                _emit_workflow_event(event)
            if isinstance(node, WorkflowNodeIr) and node_id in captured_demand_events_by_node_id:
                _replay_demand_node(node_id)
            for event in buckets.node_other_events_by_node_id.get(node_id, []):
                _emit_workflow_event(event)
            for event in buckets.node_cancelled_events_by_node_id.get(node_id, []):
                _emit_workflow_event(event)
            for event in buckets.node_end_events_by_node_id.get(node_id, []):
                _emit_workflow_event(event)

        def _resource_commit_sort_key(event: Event) -> Tuple[str, str, str]:
            payload = cast("WorkflowResourceCommitEvent", event.payload)  # pragma: allow-cast resource commit payload boundary
            return (
                str(payload.resource_type),
                str(payload.resource_id),
                str(payload.path),
            )

        for event in sorted(buckets.resource_commit_events, key=_resource_commit_sort_key):
            _emit_workflow_event(event)
        for event in buckets.unknown_node_events:
            _emit_workflow_event(event)
        for event in buckets.other_global_events:
            _emit_workflow_event(event)
        for event in buckets.finished_events:
            _emit_workflow_event(event)

    def _run_one(
        self,
        demand_ir: DemandIr,
        request: ExecutionRequest,
        workflow_node_id: str,
        visible_producer_node_ids: FrozenSet[str],
        demand_path: str,
    ) -> Union[ExecutionResult, _CapturedNodeRun]:
        def _engine_factory(**kwargs: Any) -> ScalimEngine:
            engine_kwargs = cast("Any", kwargs)  # pragma: allow-cast engine kwargs typed narrowing
            return ScalimEngine(
                **engine_kwargs,
                workflow_cache_pool=self._workflow_cache_pool,
                workflow_node_id=str(workflow_node_id),
            )

        visible = frozenset(str(x) for x in visible_producer_node_ids)
        decl_order = int(self._index_by_node_id.get(str(workflow_node_id), 0))
        try:
            demand_name = str(demand_ir.name or "")
        except AttributeError:
            demand_name = ""
        event_meta_defaults = {
            "workflow_exec_id": self._workflow_exec_id,
            "workflow_node_id": str(workflow_node_id),
            "workflow_node_decl_order": int(decl_order),
            "demand": demand_name,
            "demand_path": str(demand_path or "") or None,
        }
        with workflow_loader_context(
            workflow_exec_id=self._workflow_exec_id,
            workflow_node_id=str(workflow_node_id),
            visible_producer_node_ids=visible,
            resource_manager=self._resource_manager,
        ):
            if self._capture_observability and self._run_ir_fn is run_ir:
                core, captured_hook_events, captured_events, viz_observer = run_ir_capture_events(
                    demand_ir,
                    request,
                    engine_factory=_engine_factory,
                    event_meta_defaults=event_meta_defaults,
                )
                return _CapturedNodeRun(
                    core=core,
                    captured_hook_events=list(captured_hook_events),
                    captured_events=list(captured_events),
                    viz_observer=viz_observer,
                )
            return self._run_ir_fn(
                demand_ir,
                request,
                engine_factory=_engine_factory,
                event_meta_defaults=event_meta_defaults,
            )

    def _node_type_str(self, node: WorkflowAnyNodeIr) -> str:
        raw = node.node_type
        return str(raw.value if isinstance(raw, WorkflowNodeType) else raw)

    def _node_demand_path(self, node: WorkflowAnyNodeIr) -> Optional[str]:
        if isinstance(node, WorkflowNodeIr):
            return node.demand_path
        return None

    def _emit_workflow_node_start(self, node: WorkflowAnyNodeIr) -> None:
        node_id = str(node.node_id)
        demand_path = self._node_demand_path(node)
        stage = int(self._stage_by_node_id.get(str(node_id), 0))
        _ = self._workflow_instrumentation.emit(
            EventType.WORKFLOW_NODE_START,
            WorkflowNodeStartEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type=self._node_type_str(node),
                demand_path=str(demand_path) if demand_path is not None else None,
                schedule_mode=str(self._schedule_mode),
                stage=int(stage),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_end(self, node: WorkflowAnyNodeIr, *, status: str, exc: Optional[BaseException]) -> None:
        node_id = str(node.node_id)
        demand_path = self._node_demand_path(node)
        stage = int(self._stage_by_node_id.get(str(node_id), 0))
        error_type = None
        error_message = None
        if status != WorkflowNodeEndStatus.OK and exc is not None:
            error_type = safe_error_type(exc)
            error_message = safe_error_message(exc)
        _ = self._workflow_instrumentation.emit(
            EventType.WORKFLOW_NODE_END,
            WorkflowNodeEndEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type=self._node_type_str(node),
                status=str(status),
                demand_path=str(demand_path) if demand_path is not None else None,
                error_type=error_type,
                error_message=error_message,
                schedule_mode=str(self._schedule_mode),
                stage=int(stage),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_cancelled(self, node: WorkflowAnyNodeIr, *, reason: str, message: str) -> None:
        node_id = str(node.node_id)
        demand_path = self._node_demand_path(node)
        stage = int(self._stage_by_node_id.get(str(node_id), 0))
        _ = self._workflow_instrumentation.emit(
            EventType.WORKFLOW_NODE_CANCELLED,
            WorkflowNodeCancelledEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type=self._node_type_str(node),
                reason=str(reason),
                message=str(message),
                demand_path=str(demand_path) if demand_path is not None else None,
                schedule_mode=str(self._schedule_mode),
                stage=int(stage),
            ),
            meta={
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _cancel_node(self, node_id: str, *, reason: str, message: str) -> None:
        idx = int(self._index_by_node_id[str(node_id)])
        node = self._node_by_id[str(node_id)]
        demand_path = str(self._node_demand_path(node) or "")
        self._state.outcomes[idx] = WorkflowRunOutcome(
            run_id=str(node_id),
            demand_path=demand_path,
            result=None,
            error=WorkflowRunError(
                run_id=str(node_id),
                demand_path=demand_path,
                exc_type="WorkflowCancelled",
                message=str(message),
            ),
        )
        self._state.node_state[str(node_id)] = "cancelled"
        self._emit_workflow_node_cancelled(node, reason=reason, message=message)
        self._maybe_release_workflow_main_rows_artifact(node)
        self._resource_lifecycle.on_node_terminal(str(node_id), ok=False)

    def _on_terminal(self, node_id: str, *, ok: bool) -> None:
        for child_id in self._dependents_by_node_id.get(str(node_id), []):
            if self._state.node_state.get(str(child_id)) in {"done", "failed", "cancelled"}:
                continue
            self._state.remaining_prereqs[str(child_id)] -= 1
            if not ok:
                self._state.prereq_failed[str(child_id)] = True
            if self._state.remaining_prereqs[str(child_id)] == 0:
                if self._state.prereq_failed[str(child_id)]:
                    self._cancel_node(
                        str(child_id),
                        reason=WorkflowNodeCancelledReason.DEPENDENCY_FAILED,
                        message="Cancelled due to dependency failure",
                    )
                    self._on_terminal(str(child_id), ok=False)
                else:
                    self._state.node_state[str(child_id)] = "ready"
                    self._state.ready_queue.append(str(child_id))
                    self._state.ready_queue.sort(key=lambda nid: self._index_by_node_id.get(str(nid), 0))

    def _cancel_all_not_started_due_to_all_fail(self) -> None:
        for node in self._workflow_ir.nodes:
            if self._state.node_state.get(node.node_id) in {"pending", "ready"}:
                self._cancel_node(
                    node.node_id,
                    reason=WorkflowNodeCancelledReason.POLICY_ALL_FAIL,
                    message="Cancelled due to failure_policy=all_fail",
                )
        self._state.ready_queue = []

    def _maybe_release_workflow_managed_in_memory_output(self, node: WorkflowAnyNodeIr) -> None:
        if not isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            return  # pragma: no cover  # pragma: allow-no-cover invariant: helper called only for write nodes
        producer_node_id = str(node.input_node_id)
        output_id = str(node.input_output_id)
        key = (producer_node_id, output_id)
        remaining = self._state.write_consumers_remaining_by_output_key.get(key)
        if remaining is None:
            return
        next_remaining = int(remaining) - 1
        if next_remaining < 0:
            msg = "workflow internal error: negative write consumer count: producer_node_id={!r}, output_id={!r}".format(
                producer_node_id,
                output_id,
            )
            raise RuntimeError(msg)
        if next_remaining == 0:
            _ = self._state.write_consumers_remaining_by_output_key.pop(key, None)
            self._artifacts_dir.discard_in_memory_csv_output(producer_node_id, output_id)
            self._artifacts_dir.discard_in_memory_rows_output(producer_node_id, output_id)
            logger = get_logger("workflow.execute")
            logger.info(
                "%sreleased_managed_in_memory_output %s",
                log_prefix("workflow.execute"),
                format_kv(
                    workflow_exec_id=self._workflow_exec_id,
                    producer_node_id=str(producer_node_id),
                    output_id=str(output_id),
                    release_reason="no_remaining_consumers",
                ),
            )
        else:
            self._state.write_consumers_remaining_by_output_key[key] = int(next_remaining)

    def _maybe_release_workflow_main_rows_artifact(self, node: WorkflowAnyNodeIr) -> None:
        if not isinstance(node, WorkflowNodeIr):
            return
        producer_node_id = str(node.main_rows_from_run_id or "").strip()
        if not producer_node_id:
            return
        remaining = self._state.main_rows_consumers_remaining_by_run_id.get(producer_node_id)
        if remaining is None:
            return
        next_remaining = int(remaining) - 1
        if next_remaining < 0:
            msg = "workflow internal error: negative main_rows consumer count: producer_node_id={!r}".format(producer_node_id)
            raise RuntimeError(msg)
        if next_remaining == 0:
            _ = self._state.main_rows_consumers_remaining_by_run_id.pop(producer_node_id, None)
            self._artifacts_dir.discard(producer_node_id, "in_memory_rows")
        else:
            self._state.main_rows_consumers_remaining_by_run_id[producer_node_id] = int(next_remaining)


__all__ = ()
