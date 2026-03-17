import concurrent.futures
import contextlib
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, MutableMapping, Optional, Sequence, Tuple, cast

from ....events.catalog import (
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
    WORKFLOW_NODE_END_STATUS_ERROR,
    WORKFLOW_NODE_END_STATUS_OK,
)
from ....events.event import generate_run_id
from ....events.events import WorkflowNodeCancelledEvent, WorkflowNodeEndEvent, WorkflowNodeStartEvent
from ....execution.engine import ScalimEngine
from ....execution.preload_cache import PreloadCache
from ....execution.run_ir import ExecutionResult, run_ir
from ....hooks.base import HookManager
from ....ob.components import split_components
from ....ob.hub import InstrumentationHub
from ....ob.observability import Observability
from ....spec.ir.binding import LoaderCallContextIr
from ....typedefs import LoaderCallKwargs
from ..params_template import (
    ParamsTemplateCompileError,
    ParamsTemplateRenderError,
    compile_params_template,
)
from ..reference_syntax import parse_python_reference
from ..workflow import WorkflowConfigError, load_workflow_config, resolve_workflow_demand_path
from .compiler import compile as compile_demand
from .contracts import RunOptions, RunOverrides, RunResult
from .references import ResolverError, derive_base_module_path

_MIN_SHARED_PRELOAD_SIGNATURE_RUNS = 2


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

    runs: List[Tuple[int, str, str]] = []
    for idx, run in enumerate(wf.runs):
        demand_path = resolve_workflow_demand_path(
            run.demand,
            workflow_yaml_path=workflow_path,
            path_aliases=path_aliases,
            run_id=run.id,
        )
        runs.append((idx, str(run.id), str(demand_path)))

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

    compiled: List[Tuple[int, str, str, object]] = []
    for idx, run_id, demand_path in runs:
        compilation = compile_demand(demand_path, options=options)
        compiled.append((idx, run_id, demand_path, compilation))

    shared_cache: Optional[MutableMapping[str, Any]] = None
    if wf.options.share_preload_cache:
        _precheck_shared_preload_specs(compiled, init_vars=init_vars)
        shared_cache = PreloadCache()

    outcomes: List[Optional[WorkflowRunOutcome]] = [None for _ in range(len(compiled))]
    max_concurrency = int(wf.options.max_concurrency)
    failure_policy = str(wf.options.failure_policy or "all_fail")

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

    def _engine_factory(**kwargs: object) -> ScalimEngine:
        if shared_cache is None:
            return ScalimEngine(**cast("Any", kwargs))
        return ScalimEngine(**cast("Any", kwargs), preloaded_cache=cast("Any", shared_cache))

    def _run_one(compilation: object, workflow_node_id: str) -> ExecutionResult:
        comp = cast("Any", compilation)
        return run_ir(
            comp.demand_ir,
            comp.request,
            engine_factory=_engine_factory,
            event_meta_defaults={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )

    failed: Optional[WorkflowRunOutcome] = None
    failed_exc: Optional[BaseException] = None
    submitted: Dict["concurrent.futures.Future[ExecutionResult]", Tuple[int, str, str, object]] = {}
    pending_queue: List[Tuple[int, str, str, object]] = list(compiled)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            while pending_queue and len(submitted) < max_concurrency:
                item = pending_queue.pop(0)
                idx, run_id, demand_path, compilation = item
                _emit_workflow_node_start(run_id, demand_path=demand_path)
                fut = executor.submit(_run_one, compilation, run_id)
                submitted[fut] = item

            while submitted:
                done, _pending = concurrent.futures.wait(submitted.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    idx, run_id, demand_path, compilation = submitted.pop(fut)
                    try:
                        core = fut.result()
                        comp = cast("Any", compilation)
                        outcomes[idx] = WorkflowRunOutcome(
                            run_id=run_id,
                            demand_path=demand_path,
                            result=RunResult(core, config=comp.config, yaml_path=demand_path, sink=None),
                            error=None,
                        )
                        _emit_workflow_node_end(run_id, demand_path=demand_path, status=WORKFLOW_NODE_END_STATUS_OK, exc=None)
                    except Exception as exc:  # noqa: BLE001
                        err = WorkflowRunError(
                            run_id=run_id,
                            demand_path=demand_path,
                            exc_type=type(exc).__name__,
                            message=str(exc),
                        )
                        outcome = WorkflowRunOutcome(run_id=run_id, demand_path=demand_path, result=None, error=err)
                        outcomes[idx] = outcome
                        _emit_workflow_node_end(run_id, demand_path=demand_path, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
                        if failure_policy == "all_fail" and failed is None:
                            failed = outcome
                            failed_exc = exc
                            # 失败后不再提交新的 `run`; 同时取消尚未开始的任务.
                            for next_item in pending_queue:
                                next_idx, next_run_id, next_demand_path, _ = next_item
                                outcomes[next_idx] = WorkflowRunOutcome(
                                    run_id=next_run_id,
                                    demand_path=next_demand_path,
                                    result=None,
                                    error=WorkflowRunError(
                                        run_id=next_run_id,
                                        demand_path=next_demand_path,
                                        exc_type="WorkflowCancelled",
                                        message="Cancelled due to failure_policy=all_fail",
                                    ),
                                )
                                _emit_workflow_node_cancelled(
                                    next_run_id,
                                    demand_path=next_demand_path,
                                    reason=WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
                                    message="Cancelled due to failure_policy=all_fail",
                                )
                            pending_queue = []

                    if failed is None:
                        while pending_queue and len(submitted) < max_concurrency:
                            item = pending_queue.pop(0)
                            _idx2, run_id2, demand_path2, compilation2 = item
                            _emit_workflow_node_start(run_id2, demand_path=demand_path2)
                            fut2 = executor.submit(_run_one, compilation2, run_id2)
                            submitted[fut2] = item

        final_outcomes: List[WorkflowRunOutcome] = []
        for idx, outcome in enumerate(outcomes):
            if outcome is None:  # pragma: no cover
                run_id = str(compiled[idx][1])  # pragma: no cover
                demand_path = str(compiled[idx][2])  # pragma: no cover
                missing = WorkflowRunOutcome(  # pragma: no cover
                    run_id=run_id,
                    demand_path=demand_path,
                    result=None,
                    error=WorkflowRunError(run_id=run_id, demand_path=demand_path, exc_type="Unknown", message="Missing outcome"),
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
        with contextlib.suppress(Exception):
            workflow_observer_manager.close()


def _normalize_python_reference(reference: str, *, base_module_path: Optional[str]) -> str:
    raw = str(reference or "").strip()
    if not raw or not raw.startswith("."):
        return raw

    if base_module_path is None:
        msg = "Relative reference '{}' requires base_module_path".format(raw)
        raise ResolverError(msg)

    parsed = parse_python_reference(raw)
    absolute_module_path = _normalize_relative_module_path(parsed.module_path, base_module_path=base_module_path, reference=raw)
    if parsed.style == "class":
        return "{}:{}".format(absolute_module_path, ".".join(parsed.attr_path))
    return "{}.{}".format(absolute_module_path, parsed.entry_attr)


def _normalize_relative_module_path(module_path: str, *, base_module_path: str, reference: str) -> str:
    dot_count = 0
    for ch in module_path:
        if ch != ".":
            break
        dot_count += 1

    rest = module_path[dot_count:]
    base_parts = [p for p in str(base_module_path).split(".") if p] if base_module_path else []
    up_levels = dot_count - 1
    if up_levels > len(base_parts):
        msg = "Relative reference '{}' escapes base_module_path='{}'".format(reference, base_module_path)
        raise ResolverError(msg)

    prefix_parts = base_parts[: len(base_parts) - up_levels] if up_levels else base_parts
    rest_parts = rest.split(".")
    absolute_parts = prefix_parts + rest_parts
    return ".".join(absolute_parts)


def _render_preload_forever_params(
    source_id: str,
    *,
    params: object,
    init_vars: Optional[Dict[str, object]],
    path: str,
) -> LoaderCallKwargs:
    try:
        template = compile_params_template(
            params,
            path=path,
            init_vars=cast("Optional[Mapping[str, Any]]", init_vars),
            allow_keys=False,
            allow_rows=False,
        )
    except ParamsTemplateCompileError as exc:
        raise WorkflowConfigError(str(exc), path=path) from exc

    if template.is_empty_mapping():
        return {}

    try:
        return template.render_kwargs(LoaderCallContextIr(source_id=source_id, is_ref_loader=False), path=path)
    except ParamsTemplateRenderError as exc:
        raise WorkflowConfigError(str(exc), path=path) from exc


def _ensure_json_like(value: object, *, path: str) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_ensure_json_like(v, path=path) for v in cast("Sequence[object]", value)]
    if isinstance(value, dict):
        out: Dict[str, object] = {}
        for k, v in cast("Dict[object, object]", value).items():
            if not isinstance(k, str):
                msg = "Signature value must be JSON-like (dict key must be str)"
                raise WorkflowConfigError(msg, path=path)
            out[k] = _ensure_json_like(v, path=path)
        return out
    msg = "Signature value must be JSON-like (None/bool/int/float/str/list/tuple/dict[str, ...]), got {}".format(type(value).__name__)
    raise WorkflowConfigError(msg, path=path)


@dataclass(frozen=True)
class _PreloadSpecSignature:
    loader_ref: str
    params: object
    normalize: Optional[Dict[str, object]]
    key: object
    lookup_cast: Optional[Dict[str, object]]

    def as_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "loader_ref": self.loader_ref,
            "params": self.params,
            "normalize": self.normalize or None,
            "key": self.key,
            "lookup_cast": self.lookup_cast or None,
        }
        return payload


def _diff_signature_fields(left: _PreloadSpecSignature, right: _PreloadSpecSignature) -> List[str]:
    diff: List[str] = []
    left_dict = left.as_dict()
    right_dict = right.as_dict()
    for key in sorted(left_dict.keys()):
        if left_dict.get(key) != right_dict.get(key):
            diff.append(str(key))
    return diff


def _precheck_shared_preload_specs(  # noqa: C901
    compiled: Sequence[Tuple[int, str, str, object]],
    *,
    init_vars: Optional[Dict[str, object]],
) -> None:
    by_source: Dict[str, List[Tuple[str, str, _PreloadSpecSignature]]] = {}

    for _idx, run_id, demand_path, compilation in compiled:
        comp = cast("Any", compilation)
        config = comp.config
        yaml_path = str(demand_path)

        base_module_path: Optional[str] = None
        for source in config.sources.values():
            if str(source.cache_mode) != "preload_forever":
                continue
            if str(source.loader or "").strip().startswith("."):
                base_module_path = derive_base_module_path(yaml_path)
                break

        for source_id, source in config.sources.items():
            if str(source.cache_mode) != "preload_forever":
                continue

            loader_ref = _normalize_python_reference(str(source.loader), base_module_path=base_module_path)
            params_path = "sources.{}.params".format(source_id)
            rendered_params = _render_preload_forever_params(
                source_id,
                params=source.params,
                init_vars=init_vars,
                path=params_path,
            )

            signature = _PreloadSpecSignature(
                loader_ref=str(loader_ref),
                params=_ensure_json_like(rendered_params, path=params_path),
                normalize=_normalize_source_normalize(source.normalize, path="sources.{}.normalize".format(source_id)),
                key=_ensure_json_like(source.key, path="sources.{}.key".format(source_id)),
                lookup_cast=_normalize_source_lookup_cast(source.lookup_cast, path="sources.{}.lookup_cast".format(source_id)),
            )
            by_source.setdefault(str(source_id), []).append((run_id, yaml_path, signature))

    for source_id, items in sorted(by_source.items(), key=lambda item: str(item[0])):
        if len(items) < _MIN_SHARED_PRELOAD_SIGNATURE_RUNS:
            continue
        base_run_id, _, base_sig = items[0]
        for other_run_id, _, other_sig in items[1:]:
            if base_sig == other_sig:
                continue
            diff = _diff_signature_fields(base_sig, other_sig)
            msg = "preload_forever spec conflict for source_id='{}': run '{}' vs run '{}' (diff={})".format(
                source_id,
                base_run_id,
                other_run_id,
                ",".join(diff) if diff else "?",
            )
            raise WorkflowConfigError(
                msg,
                path="workflow.options.share_preload_cache",
            )


def _normalize_source_normalize(value: object, *, path: str) -> Optional[Dict[str, object]]:
    if value is None:
        return None
    norm = cast("Any", value)
    payload: Dict[str, object] = {
        "kind": _ensure_json_like(getattr(norm, "kind", None), path=path),
        "key_field": _ensure_json_like(getattr(norm, "key_field", None), path=path),
        "on_conflict": _ensure_json_like(getattr(norm, "on_conflict", None), path=path),
    }
    return cast("Dict[str, object]", _ensure_json_like(payload, path=path))


def _normalize_source_lookup_cast(value: object, *, path: str) -> Optional[Dict[str, object]]:
    if value is None:
        return None
    cast_cfg = cast("Any", value)
    payload: Dict[str, object] = {
        "name": _ensure_json_like(getattr(cast_cfg, "name", None), path=path),
        "sep": _ensure_json_like(getattr(cast_cfg, "sep", None), path=path),
    }
    return cast("Dict[str, object]", _ensure_json_like(payload, path=path))


__all__ = [
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunFailedError",
    "WorkflowRunOutcome",
    "run_workflow",
]
