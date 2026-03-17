import concurrent.futures
import contextlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast

from ....events.catalog import (
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED,
    WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
    WORKFLOW_NODE_END_STATUS_ERROR,
    WORKFLOW_NODE_END_STATUS_OK,
)
from ....events.event import generate_run_id
from ....events.events import WorkflowNodeCancelledEvent, WorkflowNodeEndEvent, WorkflowNodeStartEvent
from ....execution.engine import ScalimEngine
from ....execution.run_ir import ExecutionResult, run_ir
from ....execution.workflow_cache_pool import WorkflowCachePool, WorkflowCachePoolError
from ....hooks.base import HookManager
from ....ob.components import split_components
from ....ob.hub import InstrumentationHub
from ....ob.observability import Observability
from ....spec.ir.workflow import (
    WorkflowArtifactsIr,
    WorkflowCachePoolBudgetIr,
    WorkflowCachePoolIr,
    WorkflowCachePoolPinIr,
    WorkflowEdgeIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
)
from ..config_parsing.loader import YamlDemandLoader
from ..workflow import WorkflowConfigError, load_workflow_config, resolve_workflow_demand_path
from .compiler import compile as compile_demand
from .contracts import RunOptions, RunOverrides, RunResult


@dataclass(frozen=True)
class WorkflowRunError:
    run_id: str
    demand_path: str
    exc_type: str
    message: str
    diff: Optional[List[str]] = None


@dataclass(frozen=True)
class WorkflowRunOutcome:
    run_id: str
    demand_path: str
    result: Optional[RunResult] = None
    error: Optional[WorkflowRunError] = None


@dataclass(frozen=True)
class WorkflowResult:
    outcomes: Tuple[WorkflowRunOutcome, ...]

    def errors(self) -> List[WorkflowRunError]:
        rows: List[WorkflowRunError] = []
        for item in self.outcomes:
            if item.error is not None:
                rows.append(item.error)
        return rows


class _WorkflowArtifactsDirectory:
    _visible_by_consumer_node_id: Dict[str, FrozenSet[str]]
    _values_by_producer_node_id: Dict[str, Dict[str, object]]

    def __init__(self, workflow_ir: WorkflowIr) -> None:
        deps_by_node_id = {node.node_id: node.deps for node in workflow_ir.nodes}
        cache: Dict[str, Set[str]] = {}

        def _visible(node_id: str) -> Set[str]:
            cached = cache.get(node_id)
            if cached is not None:
                return cached
            out: Set[str] = set()
            for dep_id in deps_by_node_id.get(node_id, ()):
                out.add(str(dep_id))
                out.update(_visible(str(dep_id)))
            cache[node_id] = out
            return out

        visible: Dict[str, FrozenSet[str]] = {}
        for node in workflow_ir.nodes:
            visible[node.node_id] = frozenset(_visible(node.node_id))

        self._visible_by_consumer_node_id = visible
        self._values_by_producer_node_id = {}

    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]:
        return self._visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())

    def publish(self, producer_node_id: str, artifact_id: str, value: object) -> None:
        by_artifact = self._values_by_producer_node_id.setdefault(str(producer_node_id), {})
        by_artifact[str(artifact_id)] = value

    def get(self, consumer_node_id: str, producer_node_id: str, artifact_id: str) -> object:
        consumer = str(consumer_node_id)
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)

        if producer != consumer and producer not in self.visible_producer_node_ids(consumer):
            msg = "Artifact '{}' from node '{}' is not visible to node '{}' (declare deps)".format(artifact_key, producer, consumer)
            raise ValueError(msg)

        by_artifact = self._values_by_producer_node_id.get(producer)
        if by_artifact is None or artifact_key not in by_artifact:
            msg = "Unknown artifact '{}' for node '{}'".format(artifact_key, producer)
            raise KeyError(msg)
        return by_artifact[artifact_key]


class WorkflowRunFailedError(RuntimeError):
    run_id: str
    demand_path: str

    def __init__(self, message: str, *, run_id: str, demand_path: str) -> None:
        super(WorkflowRunFailedError, self).__init__(message)
        self.run_id = str(run_id)
        self.demand_path = str(demand_path)


def run_workflow(  # noqa: C901, PLR0912, PLR0915
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
    init_vars: Optional[Dict[str, object]] = None,
    path_aliases: Optional[Mapping[str, str]] = None,
) -> WorkflowResult:
    workflow_path = str(workflow_yaml_path or "").strip()
    if not workflow_path:
        msg = "workflow_yaml_path is required"
        raise WorkflowConfigError(msg, path="(file)")

    wf = load_workflow_config(workflow_path)
    workflow_exec_id = generate_run_id(prefix="wf")

    workflow_ir = _compile_workflow_ir(
        wf,
        workflow_yaml_path=workflow_path,
        path_aliases=path_aliases,
    )
    artifacts_dir = _WorkflowArtifactsDirectory(workflow_ir)

    options = RunOptions(
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
        init_vars=init_vars,
    )

    outcomes: List[Optional[WorkflowRunOutcome]] = [None for _ in range(len(workflow_ir.nodes))]
    max_concurrency = int(workflow_ir.options.max_concurrency)
    failure_policy = str(workflow_ir.options.failure_policy or "all_fail")

    # 工作流层事件:复用 `hooks`/`observers` 分发通道,并以 `workflow_exec_id` 作为 `run_id` 分区.
    component_observers, component_hooks = split_components(components)
    workflow_observer_manager = Observability().build_manager(run_id=workflow_exec_id)
    for observer in component_observers:
        workflow_observer_manager.register(observer)
    workflow_hook_manager = HookManager()
    for hook in component_hooks:
        workflow_hook_manager.register(hook)
    workflow_instrumentation = InstrumentationHub(
        hook_manager=workflow_hook_manager,
        observer_manager=workflow_observer_manager,
    )

    workflow_cache_pool: Optional[WorkflowCachePool] = None
    if workflow_ir.options.cache_pool is not None:
        logical_keys_by_node_id, consumers_by_logical_key = _derive_cache_pool_consumers(workflow_ir)
        workflow_cache_pool = WorkflowCachePool(
            workflow_exec_id=workflow_exec_id,
            instrumentation=workflow_instrumentation,
            config=workflow_ir.options.cache_pool,
            logical_keys_by_node_id=logical_keys_by_node_id,
            consumers_by_logical_key=consumers_by_logical_key,
        )

    def _emit_workflow_node_start(node_id: str, *, demand_path: str) -> None:
        _ = workflow_instrumentation.emit(
            EVENT_WORKFLOW_NODE_START,
            WorkflowNodeStartEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type="demand",
                demand_path=str(demand_path),
            ),
            meta={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_end(node_id: str, *, demand_path: str, status: str, exc: Optional[BaseException]) -> None:
        error_type = None
        error_message = None
        if status != WORKFLOW_NODE_END_STATUS_OK and exc is not None:
            error_type = type(exc).__name__
            error_message = str(exc)
        _ = workflow_instrumentation.emit(
            EVENT_WORKFLOW_NODE_END,
            WorkflowNodeEndEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type="demand",
                status=str(status),
                demand_path=str(demand_path),
                error_type=error_type,
                error_message=error_message,
            ),
            meta={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_cancelled(node_id: str, *, demand_path: str, reason: str, message: str) -> None:
        _ = workflow_instrumentation.emit(
            EVENT_WORKFLOW_NODE_CANCELLED,
            WorkflowNodeCancelledEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type="demand",
                reason=str(reason),
                message=str(message),
                demand_path=str(demand_path),
            ),
            meta={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _run_one(compilation: object, workflow_node_id: str) -> ExecutionResult:
        comp = cast("Any", compilation)

        def _engine_factory(**kwargs: object) -> ScalimEngine:
            return ScalimEngine(
                **cast("Any", kwargs),
                workflow_cache_pool=workflow_cache_pool,
                workflow_node_id=str(workflow_node_id),
            )

        return run_ir(
            comp.demand_ir,
            comp.request,
            engine_factory=_engine_factory,
            event_meta_defaults={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    node_by_id: Dict[str, WorkflowNodeIr] = {node.node_id: node for node in workflow_ir.nodes}
    index_by_node_id: Dict[str, int] = {node.node_id: int(node.decl_order) for node in workflow_ir.nodes}

    dependents_by_node_id: Dict[str, List[str]] = {}
    for node in workflow_ir.nodes:
        for dep_id in node.deps:
            dependents_by_node_id.setdefault(str(dep_id), []).append(node.node_id)
    for children in dependents_by_node_id.values():
        children.sort(key=lambda nid: index_by_node_id.get(str(nid), 0))

    node_state: Dict[str, str] = {node.node_id: "pending" for node in workflow_ir.nodes}
    remaining_prereqs: Dict[str, int] = {node.node_id: len(node.deps) for node in workflow_ir.nodes}
    prereq_failed: Dict[str, bool] = {node.node_id: False for node in workflow_ir.nodes}

    ready_queue: List[str] = []
    for node in workflow_ir.nodes:
        if remaining_prereqs.get(node.node_id, 0) == 0:
            node_state[node.node_id] = "ready"
            ready_queue.append(node.node_id)
    ready_queue.sort(key=lambda nid: index_by_node_id.get(str(nid), 0))

    failed: Optional[WorkflowRunOutcome] = None
    failed_exc: Optional[BaseException] = None
    submitted: Dict["concurrent.futures.Future[ExecutionResult]", Tuple[str, str, object]] = {}

    def _cancel_node(node_id: str, *, reason: str, message: str) -> None:
        idx = index_by_node_id[str(node_id)]
        node = node_by_id[str(node_id)]
        demand_path = str(node.demand_path or "")
        outcomes[idx] = WorkflowRunOutcome(
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
        node_state[str(node_id)] = "cancelled"
        _emit_workflow_node_cancelled(
            node_id,
            demand_path=demand_path,
            reason=reason,
            message=message,
        )
        if workflow_cache_pool is not None:
            workflow_cache_pool.on_workflow_node_done(str(node_id))

    def _on_terminal(node_id: str, *, ok: bool) -> None:
        for child_id in dependents_by_node_id.get(str(node_id), []):
            if node_state.get(str(child_id)) in {"done", "failed", "cancelled"}:
                continue
            remaining_prereqs[str(child_id)] -= 1
            if not ok:
                prereq_failed[str(child_id)] = True
            if remaining_prereqs[str(child_id)] == 0:
                if prereq_failed[str(child_id)]:
                    _cancel_node(
                        str(child_id),
                        reason=WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED,
                        message="Cancelled due to dependency failure",
                    )
                    _on_terminal(str(child_id), ok=False)
                else:
                    node_state[str(child_id)] = "ready"
                    ready_queue.append(str(child_id))
                    ready_queue.sort(key=lambda nid: index_by_node_id.get(str(nid), 0))

    def _cancel_all_not_started_due_to_all_fail() -> None:
        nonlocal ready_queue
        for node in workflow_ir.nodes:
            if node_state.get(node.node_id) in {"pending", "ready"}:
                _cancel_node(
                    node.node_id,
                    reason=WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
                    message="Cancelled due to failure_policy=all_fail",
                )
        ready_queue = []

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:

            def _try_submit_ready() -> None:
                nonlocal failed, failed_exc
                while ready_queue and len(submitted) < max_concurrency and (failed is None or failure_policy != "all_fail"):
                    node_id = ready_queue.pop(0)
                    node = node_by_id[str(node_id)]
                    demand_path = str(node.demand_path or "")

                    node_state[str(node_id)] = "running"
                    _emit_workflow_node_start(node_id, demand_path=demand_path)

                    try:
                        compilation = compile_demand(demand_path, options=options)
                    except Exception as exc:  # noqa: BLE001
                        err = WorkflowRunError(
                            run_id=str(node_id),
                            demand_path=demand_path,
                            exc_type=type(exc).__name__,
                            message=str(exc),
                        )
                        outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=demand_path, result=None, error=err)
                        outcomes[index_by_node_id[str(node_id)]] = outcome
                        node_state[str(node_id)] = "failed"
                        _emit_workflow_node_end(node_id, demand_path=demand_path, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
                        if workflow_cache_pool is not None:
                            workflow_cache_pool.on_workflow_node_done(str(node_id))
                        _on_terminal(str(node_id), ok=False)
                        if failure_policy == "all_fail" and failed is None:
                            failed = outcome
                            failed_exc = exc
                            _cancel_all_not_started_due_to_all_fail()
                        continue

                    fut = executor.submit(_run_one, compilation, str(node_id))
                    submitted[fut] = (str(node_id), demand_path, compilation)

            _try_submit_ready()

            while submitted:
                done, _pending = concurrent.futures.wait(submitted.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    node_id, demand_path, compilation = submitted.pop(fut)
                    idx = index_by_node_id.get(str(node_id), 0)
                    try:
                        core = fut.result()
                        comp = cast("Any", compilation)
                        outcomes[idx] = WorkflowRunOutcome(
                            run_id=str(node_id),
                            demand_path=str(demand_path),
                            result=RunResult(core, config=comp.config, yaml_path=str(demand_path), sink=None),
                            error=None,
                        )
                        node_state[str(node_id)] = "done"
                        _emit_workflow_node_end(str(node_id), demand_path=str(demand_path), status=WORKFLOW_NODE_END_STATUS_OK, exc=None)
                        artifacts_dir.publish(str(node_id), "output_path", core.output_path)
                        artifacts_dir.publish(str(node_id), "outputs", core.outputs)
                        if workflow_cache_pool is not None:
                            workflow_cache_pool.on_workflow_node_done(str(node_id))
                        _on_terminal(str(node_id), ok=True)
                    except Exception as exc:
                        if isinstance(exc, WorkflowCachePoolError):
                            raise WorkflowConfigError(str(exc), path=exc.path) from exc
                        err = WorkflowRunError(
                            run_id=str(node_id),
                            demand_path=str(demand_path),
                            exc_type=type(exc).__name__,
                            message=str(exc),
                        )
                        outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=str(demand_path), result=None, error=err)
                        outcomes[idx] = outcome
                        node_state[str(node_id)] = "failed"
                        _emit_workflow_node_end(str(node_id), demand_path=str(demand_path), status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
                        if workflow_cache_pool is not None:
                            workflow_cache_pool.on_workflow_node_done(str(node_id))
                        _on_terminal(str(node_id), ok=False)
                        if failure_policy == "all_fail" and failed is None:
                            failed = outcome
                            failed_exc = exc
                            _cancel_all_not_started_due_to_all_fail()

                _try_submit_ready()

        final_outcomes: List[WorkflowRunOutcome] = []
        for idx, outcome in enumerate(outcomes):
            if outcome is None:  # pragma: no cover
                node_id = str(workflow_ir.nodes[idx].node_id)  # pragma: no cover
                demand_path = str(workflow_ir.nodes[idx].demand_path)  # pragma: no cover
                missing = WorkflowRunOutcome(  # pragma: no cover
                    run_id=node_id,
                    demand_path=demand_path,
                    result=None,
                    error=WorkflowRunError(run_id=node_id, demand_path=demand_path, exc_type="Unknown", message="Missing outcome"),
                )
                final_outcomes.append(missing)  # pragma: no cover
                continue  # pragma: no cover
            final_outcomes.append(outcome)

        result = WorkflowResult(outcomes=tuple(final_outcomes))

        if failed is not None and failure_policy == "all_fail":
            msg = "Workflow run failed (run_id={}, demand_path={})".format(failed.run_id, failed.demand_path)
            exc = WorkflowRunFailedError(msg, run_id=failed.run_id, demand_path=failed.demand_path)
            if failed_exc is not None:
                exc.__cause__ = failed_exc
            raise exc

        return result
    finally:
        if workflow_cache_pool is not None:
            with contextlib.suppress(Exception):
                workflow_cache_pool.close()
        with contextlib.suppress(Exception):
            workflow_observer_manager.close()


def _compile_workflow_ir(
    wf: object,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
) -> WorkflowIr:
    wf_obj = cast("Any", wf)

    nodes: List[WorkflowNodeIr] = []
    edges: List[WorkflowEdgeIr] = []
    slots_by_node_id: Dict[str, Tuple[str, ...]] = {}

    for idx, run in enumerate(wf_obj.runs):
        demand_path = resolve_workflow_demand_path(
            run.demand,
            workflow_yaml_path=workflow_yaml_path,
            path_aliases=path_aliases,
            run_id=run.id,
        )
        node_id = str(run.id)
        deps = tuple(str(d) for d in (getattr(run, "deps", ()) or ()))
        nodes.append(
            WorkflowNodeIr(
                node_id=node_id,
                node_type=WorkflowNodeType.DEMAND,
                decl_order=int(idx),
                deps=deps,
                demand_path=str(demand_path),
            )
        )
        for dep_id in deps:
            edges.append(WorkflowEdgeIr(from_node_id=str(dep_id), to_node_id=node_id))
        slots_by_node_id[node_id] = ("output_path", "outputs")

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

    options = WorkflowOptionsIr(
        max_concurrency=int(wf_obj.options.max_concurrency),
        failure_policy=str(wf_obj.options.failure_policy or "all_fail"),
        cache_pool=cache_pool,
    )

    artifacts = WorkflowArtifactsIr(slots_by_node_id=slots_by_node_id)
    resources = cast("Dict[str, object]", getattr(wf_obj, "resources", {}) or {})

    return WorkflowIr(
        nodes=tuple(nodes),
        edges=tuple(edges),
        options=options,
        resources=resources,
        artifacts=artifacts,
    )


def _derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
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
            config = loader.load(str(demand_path))
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
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunFailedError",
    "WorkflowRunOutcome",
    "run_workflow",
]
