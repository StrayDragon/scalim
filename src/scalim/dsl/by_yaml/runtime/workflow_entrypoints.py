import concurrent.futures
import contextlib
import json
import math
import shutil
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
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
from ....ob.presets._internal import viz_config as viz_config_module
from ....ob.presets._internal.viz_config import normalize_output_dir as _normalize_viz_output_dir
from ....ob.presets.viz import (
    VizObserverConfig,
    WorkflowVizObserver,
    build_workflow_viz_graph_snapshot,
)
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
    load_workflow_config,
    resolve_workflow_demand_path,
)
from .compiler import compile as compile_demand
from .contracts import UNSET, RunOptions, RunOverrides, RunResult
from .output_composition_yaml import PathlessCsvOutputError
from .output_path_resolve import resolve_output_container_path
from .workflow_loaders import workflow_loader_context
from .workflow_resources import SheetBookDef, WorkflowResourceManager, WorkflowWriteError


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
    _lock: threading.Lock

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
        self._lock = threading.Lock()

    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]:
        return self._visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())

    def publish(self, producer_node_id: str, artifact_id: str, value: object) -> None:
        with self._lock:
            by_artifact = self._values_by_producer_node_id.setdefault(str(producer_node_id), {})
            by_artifact[str(artifact_id)] = value

    def get(self, consumer_node_id: str, producer_node_id: str, artifact_id: str) -> object:
        consumer = str(consumer_node_id)
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)

        if producer != consumer and producer not in self.visible_producer_node_ids(consumer):
            msg = "Artifact '{}' from node '{}' is not visible to node '{}' (declare deps)".format(artifact_key, producer, consumer)
            raise ValueError(msg)

        with self._lock:
            by_artifact = self._values_by_producer_node_id.get(producer)
            if by_artifact is None or artifact_key not in by_artifact:
                msg = "Unknown artifact '{}' for node '{}'".format(artifact_key, producer)
                raise KeyError(msg)
            return by_artifact[artifact_key]


def _ensure_json_like(value: object, *, path: str) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            msg = "ctx value must be JSON-like (float must be finite)"
            raise WorkflowConfigError(msg, path=path)
        return value
    if isinstance(value, list):
        return [_ensure_json_like(v, path=path) for v in cast("List[object]", value)]
    if isinstance(value, tuple):
        return [_ensure_json_like(v, path=path) for v in cast("Tuple[object, ...]", value)]
    if isinstance(value, dict):
        mapping = cast("Dict[object, object]", value)
        out: Dict[str, object] = {}
        for raw_key, raw_value in mapping.items():
            if not isinstance(raw_key, str) or not raw_key.strip():
                msg = "ctx value must be JSON-like (dict key must be non-empty str)"
                raise WorkflowConfigError(msg, path=path)
            out[str(raw_key)] = _ensure_json_like(raw_value, path=path)
        return out
    msg = "ctx value must be JSON-like (None/bool/int/float/str/list/dict[str, ...]), got {}".format(type(value).__name__)
    raise WorkflowConfigError(msg, path=path)


def _json_value_size_bytes(value: object) -> int:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return len(payload)


class _WorkflowCtxStore:
    _guardrails: WorkflowCtxOptionsIr
    _visible_by_consumer_node_id: Dict[str, FrozenSet[str]]
    _values_by_producer_node_id: Dict[str, Dict[str, object]]
    _value_bytes_by_producer_node_id: Dict[str, Dict[str, int]]
    _total_bytes: int
    _lock: threading.Lock

    def __init__(self, workflow_ir: WorkflowIr) -> None:
        self._guardrails = workflow_ir.options.ctx
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
        self._value_bytes_by_producer_node_id = {}
        self._total_bytes = 0
        self._lock = threading.Lock()

    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]:
        return self._visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())

    def publish_default_summary(self, producer_node_id: str, result: ExecutionResult) -> None:
        node_id = str(producer_node_id)
        self.publish(node_id, "output_path", result.output_path, path="workflow.options.ctx")
        self.publish(node_id, "total_rows", int(result.total_rows), path="workflow.options.ctx")
        self.publish(node_id, "duration_secs", float(result.duration), path="workflow.options.ctx")

    def publish(self, producer_node_id: str, key: str, value: object, *, path: str) -> None:
        node_id = str(producer_node_id)
        ctx_key = str(key)
        ctx_value = _ensure_json_like(value, path=path)

        value_bytes = _json_value_size_bytes(ctx_value)
        max_value_bytes = int(self._guardrails.max_value_bytes)
        if value_bytes > max_value_bytes:
            msg = "ctx value too large: node={}, key={}, bytes={} > max_value_bytes={}".format(
                node_id, ctx_key, value_bytes, max_value_bytes
            )
            raise WorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")

        with self._lock:
            by_key = self._values_by_producer_node_id.setdefault(node_id, {})
            by_key_bytes = self._value_bytes_by_producer_node_id.setdefault(node_id, {})
            prev_bytes = int(by_key_bytes.get(ctx_key, 0))

            next_total = int(self._total_bytes) - prev_bytes + int(value_bytes)
            max_bytes = int(self._guardrails.max_bytes)
            if next_total > max_bytes:
                msg = "ctx total bytes exceeded: adding node={}, key={} would make total_bytes={} > max_bytes={}".format(
                    node_id,
                    ctx_key,
                    next_total,
                    max_bytes,
                )
                raise WorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")

            by_key[ctx_key] = ctx_value
            by_key_bytes[ctx_key] = int(value_bytes)
            self._total_bytes = int(next_total)

    def resolve(self, consumer_node_id: str, *, node: str, key: str, path: str) -> object:
        consumer = str(consumer_node_id)
        producer = str(node)
        ctx_key = str(key)

        if producer == consumer:
            msg = "$ctx does not allow node=self (node_id={})".format(consumer)
            raise WorkflowConfigError(msg, path=path)

        visible = self.visible_producer_node_ids(consumer)
        if producer not in visible:
            msg = "ctx key '{}' from node '{}' is not visible to node '{}' (declare depends_on)".format(ctx_key, producer, consumer)
            raise WorkflowConfigError(msg, path=path)

        with self._lock:
            by_key = self._values_by_producer_node_id.get(producer) or {}
            if ctx_key not in by_key:
                msg = "Unknown ctx key '{}' for node '{}'".format(ctx_key, producer)
                raise WorkflowConfigError(msg, path=path)
            return by_key[ctx_key]


def _iter_ctx_directives(value: object, *, path: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if isinstance(value, dict):
        mapping = cast("Dict[object, object]", value)
        if len(mapping) == 1 and "$ctx" in mapping:
            directive = mapping.get("$ctx")
            if not isinstance(directive, dict):
                msg = "$ctx directive must be a mapping"
                raise WorkflowConfigError(msg, path=path)
            directive_dict = cast("Dict[str, object]", directive)
            node_raw = directive_dict.get("node")
            key_raw = directive_dict.get("key")
            node_id = str(node_raw or "").strip() if isinstance(node_raw, str) else ""
            ctx_key = str(key_raw or "").strip() if isinstance(key_raw, str) else ""
            if not node_id:
                msg = "$ctx.node must be a non-empty string"
                raise WorkflowConfigError(msg, path=path)
            if not ctx_key:
                msg = "$ctx.key must be a non-empty string"
                raise WorkflowConfigError(msg, path=path)
            out.append((node_id, ctx_key))
            return out
        for raw_key, raw_value in mapping.items():
            child_path = "{}.{}".format(path, str(raw_key))
            out.extend(_iter_ctx_directives(raw_value, path=child_path))
        return out

    if isinstance(value, list):
        for idx, item in enumerate(cast("List[object]", value)):
            child_path = "{}.{}".format(path, idx)
            out.extend(_iter_ctx_directives(item, path=child_path))
    return out


def _render_ctx_directives(value: object, *, consumer_node_id: str, ctx_store: _WorkflowCtxStore, path: str) -> object:
    if isinstance(value, dict):
        mapping = cast("Dict[object, object]", value)
        if len(mapping) == 1 and "$ctx" in mapping:
            directive = mapping.get("$ctx")
            if not isinstance(directive, dict):
                msg = "$ctx directive must be a mapping"
                raise WorkflowConfigError(msg, path=path)
            directive_dict = cast("Dict[str, object]", directive)
            node_raw = directive_dict.get("node")
            key_raw = directive_dict.get("key")
            node_id = str(node_raw or "").strip() if isinstance(node_raw, str) else ""
            ctx_key = str(key_raw or "").strip() if isinstance(key_raw, str) else ""
            if not node_id:
                msg = "$ctx.node must be a non-empty string"
                raise WorkflowConfigError(msg, path=path)
            if not ctx_key:
                msg = "$ctx.key must be a non-empty string"
                raise WorkflowConfigError(msg, path=path)
            value = ctx_store.resolve(str(consumer_node_id), node=node_id, key=ctx_key, path=path)
            return _ensure_json_like(value, path=path)

        out: Dict[object, object] = {}
        for raw_key, raw_value in mapping.items():
            child_path = "{}.{}".format(path, str(raw_key))
            out[raw_key] = _render_ctx_directives(raw_value, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path=child_path)
        return out

    if isinstance(value, list):
        items = cast("List[object]", value)
        return [
            _render_ctx_directives(item, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path="{}.{}".format(path, idx))
            for idx, item in enumerate(items)
        ]

    return value


def _render_workflow_init_vars(
    init_vars: Optional[Dict[str, object]],
    *,
    consumer_node_id: str,
    ctx_store: _WorkflowCtxStore,
    path_prefix: str,
) -> Dict[str, object]:
    if init_vars is None:
        return {}
    out: Dict[str, object] = {}
    for key, value in init_vars.items():
        item_path = "{}.{}".format(path_prefix, key)
        rendered = _render_ctx_directives(value, consumer_node_id=consumer_node_id, ctx_store=ctx_store, path=item_path)
        out[str(key)] = _ensure_json_like(rendered, path=item_path)
    return out


def _validate_workflow_ctx_refs(workflow_ir: WorkflowIr, *, ctx_store: _WorkflowCtxStore) -> None:
    node_ids = {str(node.node_id) for node in workflow_ir.nodes}
    for node in workflow_ir.nodes:
        node_id = str(node.node_id)
        init_vars = cast("Optional[Dict[str, object]]", getattr(node, "init_vars", None))
        if not init_vars:
            continue
        visible = ctx_store.visible_producer_node_ids(node_id)
        prefix = "workflow.runs.{}.init_vars".format(int(node.decl_order))
        for key, value in init_vars.items():
            item_path = "{}.{}".format(prefix, key)
            for ref_node_id, _ref_key in _iter_ctx_directives(value, path=item_path):
                if ref_node_id == node_id:
                    msg = "$ctx does not allow node=self (node_id={})".format(node_id)
                    raise WorkflowConfigError(msg, path=item_path)
                if ref_node_id not in node_ids:
                    msg = "Unknown ctx node '{}'".format(ref_node_id)
                    raise WorkflowConfigError(msg, path=item_path)
                if ref_node_id not in visible:
                    msg = "ctx reference to node '{}' is not visible to node '{}' (declare depends_on)".format(ref_node_id, node_id)
                    raise WorkflowConfigError(msg, path=item_path)


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
    template_vars: Optional[Mapping[str, object]] = None,
    path_aliases: Optional[Mapping[str, str]] = None,
) -> WorkflowResult:
    workflow_path = str(workflow_yaml_path or "").strip()
    if not workflow_path:
        msg = "workflow_yaml_path is required"
        raise WorkflowConfigError(msg, path="(file)")

    wf = load_workflow_config(workflow_path, template_vars=template_vars)
    workflow_exec_id = generate_run_id(prefix="wf")

    workflow_ir = _compile_workflow_ir(
        wf,
        workflow_yaml_path=workflow_path,
        path_aliases=path_aliases,
        template_vars=template_vars,
    )
    artifacts_dir = _WorkflowArtifactsDirectory(workflow_ir)
    ctx_store = _WorkflowCtxStore(workflow_ir)
    _validate_workflow_ctx_refs(workflow_ir, ctx_store=ctx_store)

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
        template_vars=template_vars,
    )

    outcomes: List[Optional[WorkflowRunOutcome]] = [None for _ in range(len(workflow_ir.nodes))]
    max_concurrency = int(workflow_ir.options.max_concurrency)
    failure_policy = str(workflow_ir.options.failure_policy or "all_fail")

    workflow_wall_start_ts = time.time()

    # 工作流 `bundle` 可视化: 通过 `run_workflow(..., overrides=RunOverrides(viz_config=...))` 显式启用.
    bundle_viz_base_config: Optional[VizObserverConfig] = None
    if overrides is not None and overrides.viz_config is not UNSET:
        viz_override = cast("Any", overrides.viz_config)
        if viz_override is not None:
            bundle_viz_base_config = cast("VizObserverConfig", viz_override)
            if bundle_viz_base_config.has_explicit_paths():
                msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`(请勿设置 `output_path`/`snapshot_path`/`trace_path`)."
                raise WorkflowConfigError(msg, path="run_workflow.overrides.viz_config")
            if not bundle_viz_base_config.output_dir and not bundle_viz_base_config.use_default_output_dir:
                msg = "工作流 `bundle` 可视化需要 `viz_config.output_dir`, 或设置 `use_default_output_dir=True`."
                raise WorkflowConfigError(msg, path="run_workflow.overrides.viz_config")

    def _bundle_run_dir(config: VizObserverConfig, run_id: str) -> Path:
        base_dir = config.output_dir
        if base_dir is None:
            base_dir = viz_config_module.default_viz_dir()
        output_dir = _normalize_viz_output_dir(str(base_dir))
        return Path(output_dir) / str(run_id)

    def _bundle_has_child_replay(config: VizObserverConfig, run_id: str) -> bool:
        run_dir = _bundle_run_dir(config, run_id)
        snapshot_path = run_dir / str(config.snapshot_filename)
        events_path = run_dir / str(config.events_filename)
        return snapshot_path.exists() and events_path.exists()

    # 工作流层事件:复用 `hooks`/`observers` 分发通道,并以 `workflow_exec_id` 作为 `run_id` 分区.
    component_observers, component_hooks = split_components(components)
    workflow_observer_manager = Observability().build_manager(run_id=workflow_exec_id)
    workflow_viz_observer: Optional[WorkflowVizObserver] = None
    for observer in component_observers:
        workflow_observer_manager.register(observer)
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
    if workflow_viz_observer is not None:
        _ = workflow_instrumentation.emit(
            "workflow_started",
            {
                "workflow_id": str(Path(workflow_path).name),
                "workflow_exec_id": str(workflow_exec_id),
                "max_concurrency": int(max_concurrency),
            },
        )

    workflow_cache_pool: Optional[WorkflowCachePool] = None
    if workflow_ir.options.cache_pool is not None:
        logical_keys_by_node_id, consumers_by_logical_key = _derive_cache_pool_consumers(workflow_ir, template_vars=template_vars)
        workflow_cache_pool = WorkflowCachePool(
            workflow_exec_id=workflow_exec_id,
            instrumentation=workflow_instrumentation,
            config=workflow_ir.options.cache_pool,
            logical_keys_by_node_id=logical_keys_by_node_id,
            consumers_by_logical_key=consumers_by_logical_key,
        )

    workbook_defs: Dict[str, str] = {}
    csv_defs: Dict[str, str] = {}
    sheetbook_defs: Dict[str, SheetBookDef] = {}
    for res in workflow_ir.resources:
        if str(res.resource_type) == "workbook":
            workbook_defs[str(res.resource_id)] = str(res.path)
        elif str(res.resource_type) == "csv":
            csv_defs[str(res.resource_id)] = str(res.path)
        elif str(res.resource_type) == "sheetbook":
            opts = res.options or {}
            budget = cast("Dict[str, object]", opts.get("budget") or {})
            max_sheets = int(cast("Any", budget.get("max_sheets") or 0))
            max_total_cells = int(cast("Any", budget.get("max_total_cells") or 0))
            export_write_lock = False
            export_cfg = opts.get("export_xlsx")
            if isinstance(export_cfg, dict):
                export_write_lock = bool(cast("Any", export_cfg).get("write_lock", False))
            export_path = str(res.path or "").strip() or None
            sheetbook_defs[str(res.resource_id)] = SheetBookDef(
                resource_id=str(res.resource_id),
                budget_max_sheets=int(max_sheets),
                budget_max_total_cells=int(max_total_cells),
                export_path=str(export_path) if export_path is not None else None,
                export_write_lock=bool(export_write_lock),
            )

    resource_manager = WorkflowResourceManager(
        workflow_exec_id=workflow_exec_id,
        instrumentation=workflow_instrumentation,
        workbook_defs=workbook_defs,
        csv_defs=csv_defs,
        sheetbook_defs=sheetbook_defs,
    )
    resources_finalized = False

    reserved_xlsx_paths: Set[str] = set()
    for res in workflow_ir.resources:
        if str(res.resource_type) not in {"workbook", "sheetbook"}:
            continue
        res_path = str(res.path or "").strip()
        if not res_path:
            continue
        reserved_xlsx_paths.add(str(Path(res_path).expanduser().resolve(strict=False)))

    workbook_writers_by_abs_path: Dict[str, List[str]] = {}

    write_output_ids_by_run_id: Dict[str, FrozenSet[str]] = {}
    tmp_write_output_ids: Dict[str, Set[str]] = {}
    for node in workflow_ir.nodes:
        if isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            tmp_write_output_ids.setdefault(str(node.input_node_id), set()).add(str(node.input_output_id))
    write_output_ids_by_run_id = {run_id: frozenset(sorted(ids)) for run_id, ids in tmp_write_output_ids.items()}

    managed_temp_dirs_by_run_id: Dict[str, Path] = {}
    wf_config_path = Path(str(workflow_path)).expanduser().resolve(strict=False)
    managed_temp_root = wf_config_path.parent / ".scalim" / "workflow" / str(workflow_exec_id) / "managed_temp_outputs"

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
                raise WorkflowConfigError(msg, path="workflow.runs[*].demand")

            existing = workbook_writers_by_abs_path.get(abs_path)
            if existing is not None and str(run_id) not in existing:
                nodes = list(existing)
                nodes.append(str(run_id))
                msg = "Excel output path collision across workflow nodes: run_id={!r}, path={!r}, nodes={}".format(
                    str(run_id),
                    str(abs_path),
                    ",".join(nodes),
                )
                raise WorkflowConfigError(msg, path="workflow.runs[*].demand")

            if existing is None:
                workbook_writers_by_abs_path[abs_path] = [str(run_id)]

    def _compile_demand_node(node: WorkflowNodeIr) -> object:
        node_id = str(node.node_id)
        demand_path = str(getattr(node, "demand_path", "") or "")

        node_options = options
        node_init_vars = _render_workflow_init_vars(
            getattr(node, "init_vars", None),
            consumer_node_id=node_id,
            ctx_store=ctx_store,
            path_prefix="workflow.runs.{}.init_vars".format(int(node.decl_order)),
        )
        if node_init_vars:
            merged = dict(options.init_vars or {})
            merged.update(node_init_vars)
            node_options = replace(node_options, init_vars=merged)

        managed_output_ids = write_output_ids_by_run_id.get(node_id)
        if managed_output_ids:
            run_temp_dir = managed_temp_root / node_id
            run_temp_dir.mkdir(parents=True, exist_ok=True)
            managed_temp_dirs_by_run_id[node_id] = run_temp_dir
            overrides = {output_id: str(run_temp_dir / "{}.csv".format(output_id)) for output_id in sorted(managed_output_ids)}
            node_options = replace(node_options, output_container_path_overrides=overrides)

        if bundle_viz_base_config is not None:
            node_viz_config = replace(bundle_viz_base_config, run_id=str(node_id))
            base_overrides = cast("RunOverrides", node_options.overrides)
            base_overrides = replace(base_overrides, viz_config=node_viz_config)
            node_options = replace(node_options, overrides=base_overrides)

        try:
            compilation = compile_demand(demand_path, options=node_options)
        except PathlessCsvOutputError as exc:
            msg = "run_id={!r}: {}".format(node_id, str(exc))
            raise WorkflowConfigError(msg, path=str(exc.config_path)) from exc

        _precheck_and_register_workbook_output_paths(
            run_id=node_id,
            demand_config=getattr(compilation, "config", None),
            init_vars=getattr(node_options, "init_vars", None),
        )
        return compilation

    def _node_type_str(node: WorkflowAnyNodeIr) -> str:
        raw = getattr(node, "node_type", "")
        return str(getattr(raw, "value", raw))

    def _emit_workflow_node_start(node: WorkflowAnyNodeIr) -> None:
        node_id = str(getattr(node, "node_id", ""))
        demand_path = getattr(node, "demand_path", None)
        _ = workflow_instrumentation.emit(
            EVENT_WORKFLOW_NODE_START,
            WorkflowNodeStartEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type=_node_type_str(node),
                demand_path=str(demand_path) if demand_path is not None else None,
            ),
            meta={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_end(node: WorkflowAnyNodeIr, *, status: str, exc: Optional[BaseException]) -> None:
        node_id = str(getattr(node, "node_id", ""))
        demand_path = getattr(node, "demand_path", None)
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
                node_type=_node_type_str(node),
                status=str(status),
                demand_path=str(demand_path) if demand_path is not None else None,
                error_type=error_type,
                error_message=error_message,
            ),
            meta={
                "workflow_exec_id": workflow_exec_id,
                "workflow_node_id": str(node_id),
            },
        )

    def _emit_workflow_node_cancelled(node: WorkflowAnyNodeIr, *, reason: str, message: str) -> None:
        node_id = str(getattr(node, "node_id", ""))
        demand_path = getattr(node, "demand_path", None)
        _ = workflow_instrumentation.emit(
            EVENT_WORKFLOW_NODE_CANCELLED,
            WorkflowNodeCancelledEvent(
                workflow_exec_id=workflow_exec_id,
                workflow_node_id=str(node_id),
                node_type=_node_type_str(node),
                reason=str(reason),
                message=str(message),
                demand_path=str(demand_path) if demand_path is not None else None,
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

        visible = ctx_store.visible_producer_node_ids(str(workflow_node_id))
        with workflow_loader_context(
            workflow_exec_id=workflow_exec_id,
            workflow_node_id=str(workflow_node_id),
            visible_producer_node_ids=visible,
            resource_manager=resource_manager,
        ):
            return run_ir(
                comp.demand_ir,
                comp.request,
                engine_factory=_engine_factory,
                event_meta_defaults={
                    "workflow_exec_id": workflow_exec_id,
                    "workflow_node_id": str(workflow_node_id),
                },
            )

    node_by_id: Dict[str, WorkflowAnyNodeIr] = {node.node_id: node for node in workflow_ir.nodes}
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
    submitted: Dict["concurrent.futures.Future[Any]", Tuple[str, WorkflowAnyNodeIr, Optional[str], Optional[object]]] = {}

    def _cancel_node(node_id: str, *, reason: str, message: str) -> None:
        idx = index_by_node_id[str(node_id)]
        node = node_by_id[str(node_id)]
        demand_path = str(getattr(node, "demand_path", "") or "")
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
        _emit_workflow_node_cancelled(node, reason=reason, message=message)
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

            def _run_write_node(node: WorkflowAnyNodeIr) -> None:  # noqa: C901, PLR0912
                if isinstance(node, WriteSheetNodeIr):
                    outputs_obj = artifacts_dir.get(str(node.node_id), str(node.input_node_id), "outputs")
                    outputs = cast("Optional[Dict[str, str]]", outputs_obj)
                    if not outputs:
                        msg = "write node requires demand outputs mapping: input_node_id={!r}".format(str(node.input_node_id))
                        raise WorkflowWriteError(msg)
                    output_path = outputs.get(str(node.input_output_id))
                    if not output_path:
                        msg = "Unknown demand output id: input_node_id={!r}, output_id={!r}".format(
                            str(node.input_node_id),
                            str(node.input_output_id),
                        )
                        raise WorkflowWriteError(msg)
                    if not str(output_path).lower().endswith(".csv"):
                        msg = "workflow writes currently only supports CSV outputs: output_path={!r}".format(str(output_path))
                        raise WorkflowWriteError(msg)
                    if str(node.resource_type) == "workbook":
                        resource_manager.apply_workbook_sheet(
                            workflow_node_id=str(node.node_id),
                            workbook_id=str(node.resource_id),
                            sheet=str(node.sheet),
                            input_node_id=str(node.input_node_id),
                            input_output_id=str(node.input_output_id),
                            input_csv_path=str(output_path),
                            on_conflict=str(node.on_conflict or "error"),
                        )
                        return
                    if str(node.resource_type) == "sheetbook":
                        resource_manager.apply_sheetbook_sheet(
                            workflow_node_id=str(node.node_id),
                            sheetbook_id=str(node.resource_id),
                            sheet=str(node.sheet),
                            input_node_id=str(node.input_node_id),
                            input_output_id=str(node.input_output_id),
                            input_csv_path=str(output_path),
                            on_conflict=str(node.on_conflict or "error"),
                        )
                        return

                    msg = "Unsupported write_sheet resource_type: {!r}".format(str(node.resource_type))  # pragma: no cover
                    raise WorkflowWriteError(msg)  # pragma: no cover

                if isinstance(node, AppendSheetNodeIr):
                    outputs_obj = artifacts_dir.get(str(node.node_id), str(node.input_node_id), "outputs")
                    outputs = cast("Optional[Dict[str, str]]", outputs_obj)
                    if not outputs:
                        msg = "append node requires demand outputs mapping: input_node_id={!r}".format(str(node.input_node_id))
                        raise WorkflowWriteError(msg)
                    output_path = outputs.get(str(node.input_output_id))
                    if not output_path:
                        msg = "Unknown demand output id: input_node_id={!r}, output_id={!r}".format(
                            str(node.input_node_id),
                            str(node.input_output_id),
                        )
                        raise WorkflowWriteError(msg)
                    if not str(output_path).lower().endswith(".csv"):
                        msg = "workflow writes currently only supports CSV outputs: output_path={!r}".format(str(output_path))
                        raise WorkflowWriteError(msg)

                    if str(node.resource_type) == "workbook":
                        if not node.sheet:  # pragma: no cover
                            msg = "append_sheet requires sheet for workbook resource (resource_id={!r})".format(
                                str(node.resource_id)
                            )  # pragma: no cover
                            raise WorkflowWriteError(msg)  # pragma: no cover
                        resource_manager.apply_workbook_append(
                            workflow_node_id=str(node.node_id),
                            workbook_id=str(node.resource_id),
                            sheet=str(node.sheet),
                            input_node_id=str(node.input_node_id),
                            input_output_id=str(node.input_output_id),
                            input_csv_path=str(output_path),
                            align_by=str(node.align_by or "field_id"),
                            header_policy=str(node.header_policy or "once"),
                            on_mismatch=str(node.on_mismatch or "error"),
                        )
                        return

                    if str(node.resource_type) == "csv":
                        resource_manager.apply_csv_append(
                            workflow_node_id=str(node.node_id),
                            csv_id=str(node.resource_id),
                            input_node_id=str(node.input_node_id),
                            input_output_id=str(node.input_output_id),
                            input_csv_path=str(output_path),
                            header_policy=str(node.header_policy or "once"),
                            on_mismatch=str(node.on_mismatch or "error"),
                        )
                        return

                    if str(node.resource_type) == "sheetbook":
                        if not node.sheet:  # pragma: no cover
                            msg = "append_sheet requires sheet for sheetbook resource (resource_id={!r})".format(
                                str(node.resource_id)
                            )  # pragma: no cover
                            raise WorkflowWriteError(msg)  # pragma: no cover
                        resource_manager.apply_sheetbook_append(
                            workflow_node_id=str(node.node_id),
                            sheetbook_id=str(node.resource_id),
                            sheet=str(node.sheet),
                            input_node_id=str(node.input_node_id),
                            input_output_id=str(node.input_output_id),
                            input_csv_path=str(output_path),
                            align_by=str(node.align_by or "field_id"),
                            header_policy=str(node.header_policy or "once"),
                            on_mismatch=str(node.on_mismatch or "error"),
                        )
                        return

                    msg = "Unsupported append_sheet resource_type: {!r}".format(str(node.resource_type))  # pragma: no cover
                    raise WorkflowWriteError(msg)  # pragma: no cover

                msg = "Unsupported workflow node type: {}".format(type(node).__name__)  # pragma: no cover
                raise WorkflowWriteError(msg)  # pragma: no cover

            def _try_submit_ready() -> None:
                nonlocal failed, failed_exc
                while ready_queue and len(submitted) < max_concurrency and (failed is None or failure_policy != "all_fail"):
                    node_id = ready_queue.pop(0)
                    node = node_by_id[str(node_id)]
                    node_state[str(node_id)] = "running"
                    _emit_workflow_node_start(node)

                    if getattr(node, "node_type", None) == WorkflowNodeType.DEMAND:
                        demand_path = str(getattr(node, "demand_path", "") or "")
                        try:
                            compilation = _compile_demand_node(cast("WorkflowNodeIr", node))
                        except WorkflowConfigError:
                            raise
                        except Exception as exc:  # noqa: BLE001
                            err = WorkflowRunError(
                                run_id=str(node_id),
                                demand_path=demand_path,
                                exc_type=type(exc).__name__,
                                message=str(exc),
                                diff=getattr(exc, "diff", None),
                            )
                            outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=demand_path, result=None, error=err)
                            outcomes[index_by_node_id[str(node_id)]] = outcome
                            node_state[str(node_id)] = "failed"
                            _emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
                            if workflow_cache_pool is not None:
                                workflow_cache_pool.on_workflow_node_done(str(node_id))
                            _on_terminal(str(node_id), ok=False)
                            if failure_policy == "all_fail" and failed is None:
                                failed = outcome
                                failed_exc = exc
                                _cancel_all_not_started_due_to_all_fail()
                            continue

                        fut = executor.submit(_run_one, compilation, str(node_id))
                        submitted[fut] = (str(node_id), node, str(demand_path), compilation)
                        continue

                    fut = executor.submit(_run_write_node, node)
                    submitted[fut] = (str(node_id), node, None, None)

            _try_submit_ready()

            while submitted:
                done, _pending = concurrent.futures.wait(submitted.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    node_id, node, demand_path, compilation = submitted.pop(fut)
                    idx = index_by_node_id.get(str(node_id), 0)
                    try:
                        result_obj = fut.result()

                        if getattr(node, "node_type", None) == WorkflowNodeType.DEMAND:
                            core = cast("ExecutionResult", result_obj)
                            comp = cast("Any", compilation)
                            demand_yaml_path = str(demand_path or "")
                            artifacts_dir.publish(str(node_id), "output_path", core.output_path)
                            artifacts_dir.publish(str(node_id), "outputs", core.outputs)
                            ctx_store.publish_default_summary(str(node_id), core)
                            outcomes[idx] = WorkflowRunOutcome(
                                run_id=str(node_id),
                                demand_path=demand_yaml_path,
                                result=RunResult(core, config=comp.config, yaml_path=demand_yaml_path, sink=None),
                                error=None,
                            )
                        else:
                            outcomes[idx] = WorkflowRunOutcome(run_id=str(node_id), demand_path="", result=None, error=None)

                        node_state[str(node_id)] = "done"
                        _emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_OK, exc=None)
                        if workflow_cache_pool is not None:
                            workflow_cache_pool.on_workflow_node_done(str(node_id))
                        _on_terminal(str(node_id), ok=True)
                    except Exception as exc:
                        if isinstance(exc, WorkflowCachePoolError):
                            raise WorkflowConfigError(str(exc), path=exc.path) from exc
                        err = WorkflowRunError(
                            run_id=str(node_id),
                            demand_path=str(demand_path or ""),
                            exc_type=type(exc).__name__,
                            message=str(exc),
                            diff=getattr(exc, "diff", None),
                        )
                        outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=str(demand_path or ""), result=None, error=err)
                        outcomes[idx] = outcome
                        node_state[str(node_id)] = "failed"
                        _emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
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
                demand_path = str(getattr(workflow_ir.nodes[idx], "demand_path", "") or "")  # pragma: no cover
                missing = WorkflowRunOutcome(  # pragma: no cover
                    run_id=node_id,
                    demand_path=demand_path,
                    result=None,
                    error=WorkflowRunError(run_id=node_id, demand_path=demand_path, exc_type="Unknown", message="Missing outcome"),
                )
                final_outcomes.append(missing)  # pragma: no cover
                continue  # pragma: no cover
            final_outcomes.append(outcome)

        try:
            has_errors = any(o.error is not None for o in final_outcomes)
            if has_errors:
                discard_node_id = failed.run_id if failed is not None else "__wf__discard"
                resource_manager.discard_all(workflow_node_id=str(discard_node_id), reason="workflow_failed")
            else:
                resource_manager.commit_all()
            resources_finalized = True
        except WorkflowWriteError as exc:
            with contextlib.suppress(Exception):
                resource_manager.discard_all(workflow_node_id="__wf__discard", reason="resource_commit_failed")
            resources_finalized = True
            raise WorkflowConfigError(str(exc), path="workflow.resources") from exc

        result = WorkflowResult(outcomes=tuple(final_outcomes))

        if failed is not None and failure_policy == "all_fail":
            msg = "工作流运行失败(run_id={}, demand_path={})".format(failed.run_id, failed.demand_path)
            exc = WorkflowRunFailedError(msg, run_id=failed.run_id, demand_path=failed.demand_path)
            if failed_exc is not None:
                exc.__cause__ = failed_exc
            raise exc

        return result
    finally:
        if workflow_viz_observer is not None and bundle_viz_base_config is not None:
            total_duration_ms = int(max(0.0, time.time() - workflow_wall_start_ts) * 1000)
            status = "error" if sys.exc_info()[1] is not None else "ok"
            with contextlib.suppress(Exception):
                _ = workflow_instrumentation.emit(
                    "workflow_finished",
                    {
                        "workflow_id": str(Path(workflow_path).name),
                        "workflow_exec_id": str(workflow_exec_id),
                        "status": status,
                        "total_duration_ms": total_duration_ms,
                    },
                )

            # 子运行完成后重写工作流快照,避免生成指向缺失子运行的下钻链接.
            with contextlib.suppress(Exception):
                demand_run_id_by_workflow_node_id: Dict[str, str] = {}
                for node in workflow_ir.nodes:
                    if getattr(node, "node_type", None) != WorkflowNodeType.DEMAND:
                        continue
                    node_id = str(getattr(node, "node_id", "") or "").strip()
                    if not node_id:
                        continue  # pragma: no cover
                    if _bundle_has_child_replay(bundle_viz_base_config, node_id):
                        demand_run_id_by_workflow_node_id[node_id] = node_id

                workflow_run_dir = _bundle_run_dir(bundle_viz_base_config, "workflow")
                workflow_run_dir.mkdir(parents=True, exist_ok=True)
                workflow_snapshot = build_workflow_viz_graph_snapshot(
                    workflow_ir,
                    demand_run_id_by_workflow_node_id=demand_run_id_by_workflow_node_id,
                    workflow_yaml_path=workflow_path,
                )
                snapshot_path = workflow_run_dir / str(bundle_viz_base_config.snapshot_filename)
                with snapshot_path.open("w", encoding="utf-8") as handle:
                    json.dump(workflow_snapshot, handle, ensure_ascii=False, indent=2, default=str)

        if not resources_finalized:
            with contextlib.suppress(Exception):
                resource_manager.discard_all(workflow_node_id="__wf__discard", reason="workflow_finally")
        if managed_temp_dirs_by_run_id:
            for temp_dir in managed_temp_dirs_by_run_id.values():
                shutil.rmtree(str(temp_dir), ignore_errors=True)
            with contextlib.suppress(Exception):
                managed_temp_root.rmdir()
            with contextlib.suppress(Exception):
                managed_temp_root.parent.rmdir()
            with contextlib.suppress(Exception):
                managed_temp_root.parent.parent.rmdir()
            with contextlib.suppress(Exception):
                managed_temp_root.parent.parent.parent.rmdir()
        if workflow_cache_pool is not None:
            with contextlib.suppress(Exception):
                workflow_cache_pool.close()
        with contextlib.suppress(Exception):
            workflow_observer_manager.close()


def _compile_workflow_ir(  # noqa: C901, PLR0912, PLR0915
    wf: object,
    *,
    workflow_yaml_path: str,
    path_aliases: Optional[Mapping[str, str]],
    template_vars: Optional[Mapping[str, object]] = None,
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
            cfg = loader.load(str(yaml_path), template_vars=template_vars)
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


def _derive_cache_pool_consumers(
    workflow_ir: WorkflowIr,
    *,
    template_vars: Optional[Mapping[str, object]],
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
            config = loader.load(str(demand_path), template_vars=template_vars)
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
