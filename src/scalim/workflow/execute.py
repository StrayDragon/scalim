import concurrent.futures
import contextlib
import json
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, cast

from ..events.catalog import (
    EVENT_WORKFLOW_NODE_CANCELLED,
    EVENT_WORKFLOW_NODE_END,
    EVENT_WORKFLOW_NODE_START,
    WORKFLOW_NODE_CANCELLED_REASON_DEPENDENCY_FAILED,
    WORKFLOW_NODE_CANCELLED_REASON_POLICY_ALL_FAIL,
    WORKFLOW_NODE_END_STATUS_ERROR,
    WORKFLOW_NODE_END_STATUS_OK,
)
from ..events.event import generate_run_id
from ..events.events import WorkflowNodeCancelledEvent, WorkflowNodeEndEvent, WorkflowNodeStartEvent
from ..exceptions import ScalimWorkflowError
from ..execution.engine import ScalimEngine
from ..execution.run_ir import ExecutionResult, run_ir
from ..execution.workflow_cache_pool import ScalimWorkflowCachePoolError, WorkflowCachePool
from ..hooks.base import HookManager
from ..ob.components import split_components
from ..ob.hub import InstrumentationHub
from ..ob.manager import ObserverManager
from ..ob.observability import Observability
from ..ob.presets._internal import viz_config as viz_config_module
from ..ob.presets._internal.viz_config import normalize_output_dir as _normalize_viz_output_dir
from ..ob.presets.viz import (
    VizObserverConfig,
    WorkflowVizObserver,
    build_workflow_viz_graph_snapshot,
)
from ..sinks.sink_rows import InMemoryRows, iter_in_memory_rows_as_main_rows
from ..spec.ir.workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WorkflowCtxOptionsIr,
    WorkflowIr,
    WorkflowNodeIr,
    WorkflowNodeType,
    WriteSheetNodeIr,
)
from ..utils.json_like import ensure_json_like as _ensure_json_like_ssot
from ..vendor.compact.typing_extensionsx import TypeGuard
from ..vendor.dataclassesx import dataclass, replace
from .errors import ScalimWorkflowConfigError
from .loaders import workflow_loader_context
from .report import WorkflowResult, WorkflowRunError, WorkflowRunOutcome
from .resources import ScalimWorkflowWriteError, SheetBookDef, WorkflowResourceManager
from .resources_csv import WorkflowCsvInput


class _CompilationLike(ABC):
    @property
    @abstractmethod
    def request(self) -> object:
        raise NotImplementedError  # pragma: no cover  # pragma: allow-no-cover abstract property


class WorkflowArtifactsDirectory:
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

    def discard(self, producer_node_id: str, artifact_id: str) -> None:
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)
        with self._lock:
            by_artifact = self._values_by_producer_node_id.get(producer)
            if not by_artifact:
                return
            _ = by_artifact.pop(artifact_key, None)
            if not by_artifact:
                _ = self._values_by_producer_node_id.pop(producer, None)

    def discard_in_memory_csv_output(self, producer_node_id: str, output_id: str) -> None:
        producer = str(producer_node_id)
        out_id = str(output_id)
        with self._lock:
            by_artifact = self._values_by_producer_node_id.get(producer)
            if not by_artifact:
                return
            mem = by_artifact.get("in_memory_csv_outputs")
            if not isinstance(mem, dict):
                return
            mem_outputs = cast("Dict[str, WorkflowCsvInput]", mem)  # pragma: allow-cast artifacts dict typed narrowing
            _ = mem_outputs.pop(out_id, None)
            if not mem_outputs:
                _ = by_artifact.pop("in_memory_csv_outputs", None)
            if not by_artifact:
                _ = self._values_by_producer_node_id.pop(producer, None)

    def discard_all_in_memory_csv_outputs(self) -> None:
        with self._lock:
            for producer_node_id, by_artifact in list(self._values_by_producer_node_id.items()):
                _ = by_artifact.pop("in_memory_csv_outputs", None)
                if not by_artifact:
                    _ = self._values_by_producer_node_id.pop(producer_node_id, None)

    def discard_all_in_memory_rows(self) -> None:
        with self._lock:
            for producer_node_id, by_artifact in list(self._values_by_producer_node_id.items()):
                _ = by_artifact.pop("in_memory_rows", None)
                if not by_artifact:
                    _ = self._values_by_producer_node_id.pop(producer_node_id, None)


def _workflow_error_diff(exc: BaseException) -> Optional[List[str]]:
    if isinstance(exc, ScalimWorkflowWriteError):
        return exc.diff
    return None


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


def _json_value_size_bytes(value: object) -> int:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return len(payload)


class WorkflowCtxStore:
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
        ctx_value = ensure_json_like(value, path=path)

        value_bytes = _json_value_size_bytes(ctx_value)
        max_value_bytes = int(self._guardrails.max_value_bytes)
        if value_bytes > max_value_bytes:
            msg = "ctx value too large: node={}, key={}, bytes={} > max_value_bytes={}".format(
                node_id, ctx_key, value_bytes, max_value_bytes
            )
            raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_value_bytes")

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
                raise ScalimWorkflowConfigError(msg, path="workflow.options.ctx.max_bytes")

            by_key[ctx_key] = ctx_value
            by_key_bytes[ctx_key] = int(value_bytes)
            self._total_bytes = int(next_total)

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

        with self._lock:
            by_key = self._values_by_producer_node_id.get(producer) or {}
            if ctx_key not in by_key:
                msg = "Unknown ctx key '{}' for node '{}'".format(ctx_key, producer)
                raise ScalimWorkflowConfigError(msg, path=path)
            return by_key[ctx_key]


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


def _is_dict_str_any(value: object) -> TypeGuard[Dict[str, Any]]:
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


def _resolve_workflow_input_csv(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    input_node_id: str,
    input_output_id: str,
    error_prefix: str,
) -> WorkflowCsvInput:
    outputs_obj = artifacts_dir.get(str(consumer_node_id), str(input_node_id), "outputs")
    outputs = cast("Optional[Dict[str, str]]", outputs_obj)  # pragma: allow-cast workflow output mapping typed narrowing
    if outputs_obj is None:
        msg = "{} requires demand outputs mapping: input_node_id={!r}".format(str(error_prefix), str(input_node_id))
        raise ScalimWorkflowWriteError(msg)

    output_id = str(input_output_id)
    output_in_mapping = False
    output_path = ""
    if outputs is not None and output_id in outputs:
        output_in_mapping = True
        output_path = str(outputs.get(output_id) or "")
    if output_path:
        if not str(output_path).lower().endswith(".csv"):
            msg = "workflow writes currently only supports CSV outputs: output_path={!r}".format(str(output_path))
            raise ScalimWorkflowWriteError(msg)
        return output_path

    mem_map_obj = None
    try:
        mem_map_obj = artifacts_dir.get(str(consumer_node_id), str(input_node_id), "in_memory_csv_outputs")
    except KeyError:
        mem_map_obj = None
    mem_map = cast("Optional[Dict[str, WorkflowCsvInput]]", mem_map_obj)  # pragma: allow-cast workflow csv mapping typed narrowing
    csv_artifact = mem_map.get(output_id) if mem_map is not None else None
    if csv_artifact is not None:
        return csv_artifact
    if output_in_mapping:
        msg = "Missing workflow-managed in-memory CSV artifact: input_node_id={!r}, output_id={!r}".format(str(input_node_id), output_id)
        raise ScalimWorkflowWriteError(msg)
    msg = "Unknown demand output id: input_node_id={!r}, output_id={!r}".format(str(input_node_id), output_id)
    raise ScalimWorkflowWriteError(msg)


def _run_workflow_write_sheet_node(
    node: WriteSheetNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    input_csv = _resolve_workflow_input_csv(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(node.node_id),
        input_node_id=str(node.input_node_id),
        input_output_id=str(node.input_output_id),
        error_prefix="write node",
    )

    if str(node.resource_type) == "workbook":
        resource_manager.apply_workbook_sheet(
            workflow_node_id=str(node.node_id),
            workbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
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
            input_csv=input_csv,
            on_conflict=str(node.on_conflict or "error"),
        )
        return

    msg = "Unsupported write_sheet resource_type: {!r}".format(
        str(node.resource_type)
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


def _run_workflow_append_sheet_node(
    node: AppendSheetNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    input_csv = _resolve_workflow_input_csv(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(node.node_id),
        input_node_id=str(node.input_node_id),
        input_output_id=str(node.input_output_id),
        error_prefix="append node",
    )

    if str(node.resource_type) == "workbook":
        if not node.sheet:  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            msg = "append_sheet requires sheet for workbook resource (resource_id={!r})".format(
                str(node.resource_id)
            )  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
        resource_manager.apply_workbook_append(
            workflow_node_id=str(node.node_id),
            workbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
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
            input_csv=input_csv,
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    if str(node.resource_type) == "sheetbook":
        if not node.sheet:  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            msg = "append_sheet requires sheet for sheetbook resource (resource_id={!r})".format(
                str(node.resource_id)
            )  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
        resource_manager.apply_sheetbook_append(
            workflow_node_id=str(node.node_id),
            sheetbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            align_by=str(node.align_by or "field_id"),
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    msg = "Unsupported append_sheet resource_type: {!r}".format(
        str(node.resource_type)
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


def _run_workflow_write_node(
    node: WorkflowAnyNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    if isinstance(node, WriteSheetNodeIr):
        _run_workflow_write_sheet_node(
            node,
            artifacts_dir=artifacts_dir,
            resource_manager=resource_manager,
        )
        return

    if isinstance(node, AppendSheetNodeIr):
        _run_workflow_append_sheet_node(
            node,
            artifacts_dir=artifacts_dir,
            resource_manager=resource_manager,
        )
        return

    msg = "Unsupported workflow node type: {}".format(
        type(node).__name__
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


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


@dataclass
class _PreparedWorkflowRun:
    workflow_path: str
    workflow_exec_id: str
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
    write_output_ids_by_run_id: Dict[str, FrozenSet[str]]
    write_consumers_remaining_by_output_key: Dict[Tuple[str, str], int]
    main_rows_consumers_remaining_by_run_id: Dict[str, int]


def _build_workflow_instrumentation(
    *,
    workflow_exec_id: str,
    workflow_path: str,
    workflow_ir: WorkflowIr,
    max_concurrency: int,
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
        if workflow_viz_observer is not None:
            _ = workflow_instrumentation.emit(
                "workflow_started",
                {
                    "workflow_id": str(Path(workflow_path).name),
                    "workflow_exec_id": str(workflow_exec_id),
                    "max_concurrency": int(max_concurrency),
                },
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
        raise ScalimWorkflowConfigError(msg, path="workflow.options.cache_pool")
    return WorkflowCachePool(
        workflow_exec_id=workflow_exec_id,
        instrumentation=workflow_instrumentation,
        config=cache_pool_ir,
        logical_keys_by_node_id=logical_keys_by_node_id,
        consumers_by_logical_key=consumers_by_logical_key,
    )


def _build_workflow_resource_defs(
    workflow_ir: WorkflowIr,
) -> Tuple[Dict[str, str], Dict[str, bool], Dict[str, str], Dict[str, SheetBookDef]]:
    workbook_defs: Dict[str, str] = {}
    workbook_allow_formulas_by_id: Dict[str, bool] = {}
    csv_defs: Dict[str, str] = {}
    sheetbook_defs: Dict[str, SheetBookDef] = {}

    for res in workflow_ir.resources:
        res_type = str(res.resource_type)
        if res_type == "workbook":
            workbook_defs[str(res.resource_id)] = str(res.path)
            opts = res.options or {}
            allow_formulas = False
            if isinstance(opts, dict):
                allow_formulas = bool(opts.get("allow_formulas", False))
            workbook_allow_formulas_by_id[str(res.resource_id)] = bool(allow_formulas)
            continue

        if res_type == "csv":
            csv_defs[str(res.resource_id)] = str(res.path)
            continue

        if res_type == "sheetbook":
            opts = res.options or {}
            budget_obj = opts.get("budget")
            budget: Dict[str, Any] = budget_obj if _is_dict_str_any(budget_obj) else {}
            max_sheets = int(budget.get("max_sheets") or 0)
            max_total_cells = int(budget.get("max_total_cells") or 0)

            export_cfg_obj = opts.get("export_xlsx")
            export_cfg: Dict[str, Any] = export_cfg_obj if _is_dict_str_any(export_cfg_obj) else {}
            export_write_lock = bool(export_cfg.get("write_lock", False))
            export_allow_formulas = bool(export_cfg.get("allow_formulas", False))
            export_path = str(res.path or "").strip() or None
            sheetbook_defs[str(res.resource_id)] = SheetBookDef(
                resource_id=str(res.resource_id),
                budget_max_sheets=int(max_sheets),
                budget_max_total_cells=int(max_total_cells),
                export_path=str(export_path) if export_path is not None else None,
                export_write_lock=bool(export_write_lock),
                export_allow_formulas=bool(export_allow_formulas),
            )
            continue

    return workbook_defs, workbook_allow_formulas_by_id, csv_defs, sheetbook_defs


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
    failure_policy = str(workflow_ir.options.failure_policy or "all_fail")
    workflow_wall_start_ts = time.time()

    workflow_observer_manager: Optional[ObserverManager] = None
    workflow_cache_pool: Optional[WorkflowCachePool] = None
    try:
        workflow_observer_manager, workflow_viz_observer, workflow_instrumentation = _build_workflow_instrumentation(
            workflow_exec_id=workflow_exec_id,
            workflow_path=workflow_path,
            workflow_ir=workflow_ir,
            max_concurrency=int(max_concurrency),
            components=components,
            bundle_viz_base_config=bundle_viz_base_config,
        )
        workflow_cache_pool = _maybe_build_workflow_cache_pool(
            workflow_exec_id=workflow_exec_id,
            workflow_ir=workflow_ir,
            workflow_instrumentation=workflow_instrumentation,
            logical_keys_by_node_id=cache_pool_logical_keys_by_node_id,
            consumers_by_logical_key=cache_pool_consumers_by_logical_key,
        )

        workbook_defs, workbook_allow_formulas_by_id, csv_defs, sheetbook_defs = _build_workflow_resource_defs(workflow_ir)
        resource_manager = WorkflowResourceManager(
            workflow_exec_id=workflow_exec_id,
            instrumentation=workflow_instrumentation,
            workbook_defs=workbook_defs,
            workbook_allow_formulas=workbook_allow_formulas_by_id,
            csv_defs=csv_defs,
            sheetbook_defs=sheetbook_defs,
        )

        write_output_ids_by_run_id = _build_write_output_ids_by_run_id(workflow_ir)
        write_consumers_remaining_by_output_key = _build_write_consumers_remaining_by_output_key(workflow_ir)
        main_rows_consumers_remaining_by_run_id = _build_main_rows_consumers_remaining_by_run_id(workflow_ir)

        return _PreparedWorkflowRun(
            workflow_path=workflow_path,
            workflow_exec_id=workflow_exec_id,
            workflow_ir=workflow_ir,
            artifacts_dir=artifacts_dir,
            ctx_store=ctx_store,
            max_concurrency=int(max_concurrency),
            failure_policy=str(failure_policy),
            workflow_wall_start_ts=float(workflow_wall_start_ts),
            bundle_viz_base_config=bundle_viz_base_config,
            workflow_observer_manager=workflow_observer_manager,
            workflow_viz_observer=workflow_viz_observer,
            workflow_instrumentation=workflow_instrumentation,
            workflow_cache_pool=workflow_cache_pool,
            resource_manager=resource_manager,
            write_output_ids_by_run_id=write_output_ids_by_run_id,
            write_consumers_remaining_by_output_key=write_consumers_remaining_by_output_key,
            main_rows_consumers_remaining_by_run_id=main_rows_consumers_remaining_by_run_id,
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
) -> object:
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
    request = comp.request
    next_request = request
    if node_id in main_rows_consumers_remaining_by_run_id:
        next_request = replace(next_request, capture_in_memory_rows=True)

    producer_run_id = str(node.main_rows_from_run_id or "").strip()
    if producer_run_id:
        typed_rows_obj = artifacts_dir.get(str(node_id), producer_run_id, "in_memory_rows")
        if not isinstance(typed_rows_obj, InMemoryRows):
            msg = "Missing workflow-managed typed rows artifact: producer_node_id={!r}".format(producer_run_id)
            raise ScalimWorkflowWriteError(msg)
        next_request = replace(next_request, main_rows=iter_in_memory_rows_as_main_rows(typed_rows_obj))

    if next_request is request:
        return compilation
    return replace(compilation, request=next_request)


def _workflow_try_submit_ready(  # noqa: PLR0913
    executor: concurrent.futures.ThreadPoolExecutor,
    *,
    ready_queue: List[str],
    submitted: Dict["concurrent.futures.Future[Any]", Tuple[str, WorkflowAnyNodeIr, Optional[str], Optional[object]]],
    max_concurrency: int,
    failure_policy: str,
    failed_outcome_holder: List[Optional[WorkflowRunOutcome]],
    failed_exc_holder: List[Optional[BaseException]],
    node_by_id: Dict[str, WorkflowAnyNodeIr],
    node_state: Dict[str, str],
    index_by_node_id: Dict[str, int],
    outcomes: List[Optional[WorkflowRunOutcome]],
    workflow_exec_id: str,
    workflow_cache_pool: Optional[WorkflowCachePool],
    compile_demand_fn: Callable[..., object],
    artifacts_dir: WorkflowArtifactsDirectory,
    ctx_store: WorkflowCtxStore,
    bundle_viz_base_config: Optional[VizObserverConfig],
    write_output_ids_by_run_id: Dict[str, FrozenSet[str]],
    main_rows_consumers_remaining_by_run_id: Dict[str, int],
    resource_manager: WorkflowResourceManager,
    run_one: Callable[[object, str], ExecutionResult],
    emit_workflow_node_start: Callable[[WorkflowAnyNodeIr], None],
    emit_workflow_node_end: Callable[..., None],
    maybe_release_workflow_main_rows_artifact: Callable[[WorkflowAnyNodeIr], None],
    on_terminal: Callable[..., None],
    cancel_all_not_started_due_to_all_fail: Callable[[], None],
) -> None:
    while ready_queue and len(submitted) < max_concurrency and (failed_outcome_holder[0] is None or failure_policy != "all_fail"):
        node_id = ready_queue.pop(0)
        node = node_by_id[str(node_id)]
        node_state[str(node_id)] = "running"
        emit_workflow_node_start(node)

        if isinstance(node, WorkflowNodeIr):
            demand_path = str(node.demand_path or "")
            try:
                compilation = _compile_demand_node(
                    node,
                    workflow_exec_id=str(workflow_exec_id),
                    ctx_store=ctx_store,
                    compile_demand_fn=compile_demand_fn,
                    bundle_viz_base_config=bundle_viz_base_config,
                    write_output_ids_by_run_id=write_output_ids_by_run_id,
                    main_rows_consumers_remaining_by_run_id=main_rows_consumers_remaining_by_run_id,
                    artifacts_dir=artifacts_dir,
                )
            except ScalimWorkflowConfigError:
                raise
            except Exception as exc:  # noqa: BLE001
                err = WorkflowRunError(
                    run_id=str(node_id),
                    demand_path=demand_path,
                    exc_type=type(exc).__name__,
                    message=str(exc),
                    diff=_workflow_error_diff(exc),
                )
                outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=demand_path, result=None, error=err)
                outcomes[index_by_node_id[str(node_id)]] = outcome
                node_state[str(node_id)] = "failed"
                emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
                maybe_release_workflow_main_rows_artifact(node)
                if workflow_cache_pool is not None:
                    workflow_cache_pool.on_workflow_node_done(str(node_id))
                on_terminal(str(node_id), ok=False)
                if failure_policy == "all_fail" and failed_outcome_holder[0] is None:
                    failed_outcome_holder[0] = outcome
                    failed_exc_holder[0] = exc
                    cancel_all_not_started_due_to_all_fail()
                continue

            fut = executor.submit(run_one, compilation, str(node_id))
            submitted[fut] = (str(node_id), node, str(demand_path), compilation)
            continue

        fut = executor.submit(
            _run_workflow_write_node,
            node,
            artifacts_dir=artifacts_dir,
            resource_manager=resource_manager,
        )
        submitted[fut] = (str(node_id), node, None, None)


def _workflow_process_completed_future(  # noqa: PLR0913
    fut: "concurrent.futures.Future[Any]",
    *,
    node_id: str,
    node: WorkflowAnyNodeIr,
    demand_path: Optional[str],
    compilation: Optional[object],
    idx: int,
    outcomes: List[Optional[WorkflowRunOutcome]],
    node_state: Dict[str, str],
    workflow_exec_id: str,
    artifacts_dir: WorkflowArtifactsDirectory,
    ctx_store: WorkflowCtxStore,
    build_demand_run_result_fn: Optional[Callable[..., object]],
    workflow_cache_pool: Optional[WorkflowCachePool],
    failure_policy: str,
    failed_outcome_holder: List[Optional[WorkflowRunOutcome]],
    failed_exc_holder: List[Optional[BaseException]],
    emit_workflow_node_end: Callable[..., None],
    maybe_release_workflow_managed_in_memory_output: Callable[[WorkflowAnyNodeIr], None],
    maybe_release_workflow_main_rows_artifact: Callable[[WorkflowAnyNodeIr], None],
    on_terminal: Callable[..., None],
    cancel_all_not_started_due_to_all_fail: Callable[[], None],
) -> None:
    try:
        result_obj = fut.result()

        if isinstance(node, WorkflowNodeIr):
            core = cast("ExecutionResult", result_obj)  # pragma: allow-cast future result typed narrowing
            demand_yaml_path = str(demand_path or "")
            artifacts_dir.publish(str(node_id), "output_path", core.output_path)
            artifacts_dir.publish(str(node_id), "outputs", core.outputs)
            artifacts_dir.publish(str(node_id), "in_memory_csv_outputs", core.in_memory_csv_outputs or {})
            if core.in_memory_rows is not None:
                artifacts_dir.publish(str(node_id), "in_memory_rows", core.in_memory_rows)
            ctx_store.publish_default_summary(str(node_id), core)
            if build_demand_run_result_fn is None:
                node_result: object = core
            else:
                node_result = build_demand_run_result_fn(
                    core,
                    compilation=compilation,
                    demand_yaml_path=demand_yaml_path,
                    workflow_exec_id=str(workflow_exec_id),
                    workflow_node_id=str(node_id),
                )
            outcomes[idx] = WorkflowRunOutcome(
                run_id=str(node_id),
                demand_path=demand_yaml_path,
                result=node_result,
                error=None,
            )
        else:
            maybe_release_workflow_managed_in_memory_output(node)
            outcomes[idx] = WorkflowRunOutcome(run_id=str(node_id), demand_path="", result=None, error=None)

        maybe_release_workflow_main_rows_artifact(node)
        node_state[str(node_id)] = "done"
        emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_OK, exc=None)
        if workflow_cache_pool is not None:
            workflow_cache_pool.on_workflow_node_done(str(node_id))
        on_terminal(str(node_id), ok=True)
    except Exception as exc:
        if isinstance(exc, ScalimWorkflowCachePoolError):
            raise ScalimWorkflowConfigError(str(exc), path=exc.path) from exc
        err = WorkflowRunError(
            run_id=str(node_id),
            demand_path=str(demand_path or ""),
            exc_type=type(exc).__name__,
            message=str(exc),
            diff=_workflow_error_diff(exc),
        )
        outcome = WorkflowRunOutcome(run_id=str(node_id), demand_path=str(demand_path or ""), result=None, error=err)
        outcomes[idx] = outcome
        node_state[str(node_id)] = "failed"
        emit_workflow_node_end(node, status=WORKFLOW_NODE_END_STATUS_ERROR, exc=exc)
        maybe_release_workflow_main_rows_artifact(node)
        if workflow_cache_pool is not None:
            workflow_cache_pool.on_workflow_node_done(str(node_id))
        on_terminal(str(node_id), ok=False)
        if failure_policy == "all_fail" and failed_outcome_holder[0] is None:
            failed_outcome_holder[0] = outcome
            failed_exc_holder[0] = exc
            cancel_all_not_started_due_to_all_fail()


def _execute_workflow_run(  # noqa: C901, PLR0915
    prepared: _PreparedWorkflowRun,
    *,
    compile_demand_fn: Callable[..., object],
    build_demand_run_result_fn: Optional[Callable[..., object]],
    run_ir_fn: Callable[..., ExecutionResult],
) -> Tuple[List[WorkflowRunOutcome], Optional[WorkflowRunOutcome], Optional[BaseException]]:
    workflow_exec_id = prepared.workflow_exec_id
    workflow_ir = prepared.workflow_ir
    artifacts_dir = prepared.artifacts_dir
    ctx_store = prepared.ctx_store
    max_concurrency = int(prepared.max_concurrency)
    failure_policy = str(prepared.failure_policy or "all_fail")
    bundle_viz_base_config = prepared.bundle_viz_base_config
    workflow_instrumentation = prepared.workflow_instrumentation
    workflow_cache_pool = prepared.workflow_cache_pool
    resource_manager = prepared.resource_manager
    write_output_ids_by_run_id = prepared.write_output_ids_by_run_id
    write_consumers_remaining_by_output_key = prepared.write_consumers_remaining_by_output_key
    main_rows_consumers_remaining_by_run_id = prepared.main_rows_consumers_remaining_by_run_id

    outcomes: List[Optional[WorkflowRunOutcome]] = [None for _ in range(len(workflow_ir.nodes))]
    failed_outcome_holder: List[Optional[WorkflowRunOutcome]] = [None]
    failed_exc_holder: List[Optional[BaseException]] = [None]

    def _maybe_release_workflow_managed_in_memory_output(node: WorkflowAnyNodeIr) -> None:
        if not isinstance(node, (WriteSheetNodeIr, AppendSheetNodeIr)):
            return  # pragma: no cover  # pragma: allow-no-cover invariant: helper called only for write nodes
        producer_node_id = str(node.input_node_id)
        output_id = str(node.input_output_id)
        key = (producer_node_id, output_id)
        remaining = write_consumers_remaining_by_output_key.get(key)
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
            _ = write_consumers_remaining_by_output_key.pop(key, None)
            artifacts_dir.discard_in_memory_csv_output(producer_node_id, output_id)
        else:
            write_consumers_remaining_by_output_key[key] = int(next_remaining)

    def _maybe_release_workflow_main_rows_artifact(node: WorkflowAnyNodeIr) -> None:
        if not isinstance(node, WorkflowNodeIr):
            return
        producer_node_id = str(node.main_rows_from_run_id or "").strip()
        if not producer_node_id:
            return
        remaining = main_rows_consumers_remaining_by_run_id.get(producer_node_id)
        if remaining is None:
            return
        next_remaining = int(remaining) - 1
        if next_remaining < 0:
            msg = "workflow internal error: negative main_rows consumer count: producer_node_id={!r}".format(producer_node_id)
            raise RuntimeError(msg)
        if next_remaining == 0:
            _ = main_rows_consumers_remaining_by_run_id.pop(producer_node_id, None)
            artifacts_dir.discard(producer_node_id, "in_memory_rows")
        else:
            main_rows_consumers_remaining_by_run_id[producer_node_id] = int(next_remaining)

    def _node_type_str(node: WorkflowAnyNodeIr) -> str:
        raw = node.node_type
        return str(raw.value if isinstance(raw, WorkflowNodeType) else raw)

    def _node_demand_path(node: WorkflowAnyNodeIr) -> Optional[str]:
        if isinstance(node, WorkflowNodeIr):
            return node.demand_path
        return None

    def _emit_workflow_node_start(node: WorkflowAnyNodeIr) -> None:
        node_id = str(node.node_id)
        demand_path = _node_demand_path(node)
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
        node_id = str(node.node_id)
        demand_path = _node_demand_path(node)
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
        node_id = str(node.node_id)
        demand_path = _node_demand_path(node)
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
        comp = cast("Any", compilation)  # pragma: allow-cast compilation runtime boundary

        def _engine_factory(**kwargs: object) -> ScalimEngine:
            engine_kwargs = cast("Any", kwargs)  # pragma: allow-cast engine kwargs typed narrowing
            return ScalimEngine(
                **engine_kwargs,
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
            return run_ir_fn(
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

    submitted: Dict["concurrent.futures.Future[Any]", Tuple[str, WorkflowAnyNodeIr, Optional[str], Optional[object]]] = {}

    def _cancel_node(node_id: str, *, reason: str, message: str) -> None:
        idx = index_by_node_id[str(node_id)]
        node = node_by_id[str(node_id)]
        demand_path = str(_node_demand_path(node) or "")
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
        _maybe_release_workflow_main_rows_artifact(node)
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as executor:

        def _try_submit_ready() -> None:
            _workflow_try_submit_ready(
                executor,
                ready_queue=ready_queue,
                submitted=submitted,
                max_concurrency=max_concurrency,
                failure_policy=failure_policy,
                failed_outcome_holder=failed_outcome_holder,
                failed_exc_holder=failed_exc_holder,
                node_by_id=node_by_id,
                node_state=node_state,
                index_by_node_id=index_by_node_id,
                outcomes=outcomes,
                workflow_exec_id=str(workflow_exec_id),
                workflow_cache_pool=workflow_cache_pool,
                compile_demand_fn=compile_demand_fn,
                artifacts_dir=artifacts_dir,
                ctx_store=ctx_store,
                bundle_viz_base_config=bundle_viz_base_config,
                write_output_ids_by_run_id=write_output_ids_by_run_id,
                main_rows_consumers_remaining_by_run_id=main_rows_consumers_remaining_by_run_id,
                resource_manager=resource_manager,
                run_one=_run_one,
                emit_workflow_node_start=_emit_workflow_node_start,
                emit_workflow_node_end=_emit_workflow_node_end,
                maybe_release_workflow_main_rows_artifact=_maybe_release_workflow_main_rows_artifact,
                on_terminal=_on_terminal,
                cancel_all_not_started_due_to_all_fail=_cancel_all_not_started_due_to_all_fail,
            )

        _try_submit_ready()

        while submitted:
            done, _pending = concurrent.futures.wait(submitted.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                node_id, node, demand_path, compilation = submitted.pop(fut)
                idx = index_by_node_id.get(str(node_id), 0)
                _workflow_process_completed_future(
                    fut,
                    node_id=str(node_id),
                    node=node,
                    demand_path=demand_path,
                    compilation=compilation,
                    idx=idx,
                    outcomes=outcomes,
                    node_state=node_state,
                    workflow_exec_id=str(workflow_exec_id),
                    artifacts_dir=artifacts_dir,
                    ctx_store=ctx_store,
                    build_demand_run_result_fn=build_demand_run_result_fn,
                    workflow_cache_pool=workflow_cache_pool,
                    failure_policy=failure_policy,
                    failed_outcome_holder=failed_outcome_holder,
                    failed_exc_holder=failed_exc_holder,
                    emit_workflow_node_end=_emit_workflow_node_end,
                    maybe_release_workflow_managed_in_memory_output=_maybe_release_workflow_managed_in_memory_output,
                    maybe_release_workflow_main_rows_artifact=_maybe_release_workflow_main_rows_artifact,
                    on_terminal=_on_terminal,
                    cancel_all_not_started_due_to_all_fail=_cancel_all_not_started_due_to_all_fail,
                )

            _try_submit_ready()

    final_outcomes: List[WorkflowRunOutcome] = []
    for idx, outcome in enumerate(outcomes):
        if outcome is None:  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
            node_id = str(workflow_ir.nodes[idx].node_id)  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
            demand_path = str(
                _node_demand_path(workflow_ir.nodes[idx]) or ""
            )  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
            missing = WorkflowRunOutcome(  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
                run_id=node_id,
                demand_path=demand_path,
                result=None,
                error=WorkflowRunError(run_id=node_id, demand_path=demand_path, exc_type="Unknown", message="Missing outcome"),
            )
            final_outcomes.append(missing)  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
            continue  # pragma: no cover  # pragma: allow-no-cover unreachable: outcome always set
        final_outcomes.append(outcome)

    return final_outcomes, failed_outcome_holder[0], failed_exc_holder[0]


def _commit_workflow_resources(
    *,
    resource_manager: WorkflowResourceManager,
    outcomes: List[WorkflowRunOutcome],
    failed: Optional[WorkflowRunOutcome],
) -> None:
    try:
        has_errors = any(o.error is not None for o in outcomes)
        if has_errors:
            discard_node_id = failed.run_id if failed is not None else "__wf__discard"
            resource_manager.discard_all(workflow_node_id=str(discard_node_id), reason="workflow_failed")
        else:
            resource_manager.commit_all()
    except ScalimWorkflowWriteError as exc:
        with contextlib.suppress(Exception):
            resource_manager.discard_all(workflow_node_id="__wf__discard", reason="resource_commit_failed")
        raise ScalimWorkflowConfigError(str(exc), path="workflow.resources") from exc


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
        demand_run_id_by_workflow_node_id: Dict[str, str] = {}
        for node in prepared.workflow_ir.nodes:
            if not isinstance(node, WorkflowNodeIr):
                continue
            node_id = str(node.node_id or "").strip()
            if not node_id:
                continue  # pragma: no cover  # pragma: allow-no-cover unreachable: node_id required by IR
            if _bundle_has_child_replay(prepared.bundle_viz_base_config, node_id):
                demand_run_id_by_workflow_node_id[node_id] = node_id

        workflow_run_dir = _bundle_run_dir(prepared.bundle_viz_base_config, "workflow")
        workflow_run_dir.mkdir(parents=True, exist_ok=True)
        workflow_snapshot = build_workflow_viz_graph_snapshot(
            prepared.workflow_ir,
            demand_run_id_by_workflow_node_id=demand_run_id_by_workflow_node_id,
            workflow_yaml_path=prepared.workflow_path,
        )
        snapshot_path = workflow_run_dir / str(prepared.bundle_viz_base_config.snapshot_filename)
        with snapshot_path.open("w", encoding="utf-8") as handle:
            json.dump(workflow_snapshot, handle, ensure_ascii=False, indent=2, default=str)


def _cleanup_workflow_finally(prepared: _PreparedWorkflowRun, *, resources_finalized: bool) -> None:
    if not resources_finalized:
        with contextlib.suppress(Exception):
            prepared.resource_manager.discard_all(workflow_node_id="__wf__discard", reason="workflow_finally")
    with contextlib.suppress(Exception):
        prepared.artifacts_dir.discard_all_in_memory_csv_outputs()
    with contextlib.suppress(Exception):
        prepared.artifacts_dir.discard_all_in_memory_rows()
    if prepared.workflow_cache_pool is not None:
        with contextlib.suppress(Exception):
            prepared.workflow_cache_pool.close()
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
            _commit_workflow_resources(
                resource_manager=prepared.resource_manager,
                outcomes=final_outcomes,
                failed=failed,
            )
            resources_finalized = True
        except ScalimWorkflowConfigError:
            resources_finalized = True
            raise

        result = WorkflowResult(outcomes=tuple(final_outcomes))
        if failed is not None and prepared.failure_policy == "all_fail":
            msg = "工作流运行失败(run_id={}, demand_path={})".format(failed.run_id, failed.demand_path)
            exc = ScalimWorkflowRunFailedError(msg, run_id=failed.run_id, demand_path=failed.demand_path)
            if failed_exc is not None:
                exc.__cause__ = failed_exc
            raise exc
        return result
    finally:
        if prepared is not None:
            _report_workflow_viz_finished(prepared)
            _cleanup_workflow_finally(prepared, resources_finalized=resources_finalized)


__all__ = [
    "ScalimWorkflowRunFailedError",
    "WorkflowResult",
    "WorkflowRunError",
    "WorkflowRunOutcome",
    "run_workflow_ir",
]
