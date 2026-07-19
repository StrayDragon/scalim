import hashlib
import json
import threading
from collections import OrderedDict
from typing import Callable, Dict, FrozenSet, List, Mapping, Optional, Set, Tuple, cast, overload

from .._internal.utils.json_like import JsonLike
from .._internal.utils.json_like import ensure_json_like as _ensure_json_like_ssot
from ..events import EventType
from ..events._events import (
    DiagnosticWarningEvent,
    WorkflowCacheAcquireEvent,
    WorkflowCacheEvictEvent,
    WorkflowCacheReleaseEvent,
)
from ..exceptions import ScalimExecutionError
from ..ob.hub import InstrumentationHub
from ..spec.ir import SourceIr
from ..spec.ir._workflow import WorkflowCachePoolIr
from ..spec.ir.callable_refs import describe_callable_ref
from ..spec.ir.lookup_casts import LookupCastSpecIr
from ..typedefs import LoaderCallKwargs, LoaderResultMapping, RuntimeValue
from ..vendor.compact.typing_extensionsx import TypeGuard
from ..vendor.dataclassesx import dataclass, field


class ScalimWorkflowCachePoolError(ScalimExecutionError):
    path: str

    def __init__(self, message: str, *, path: str) -> None:
        super(ScalimWorkflowCachePoolError, self).__init__(str(message))
        self.path = str(path or "")


def _is_list(value: RuntimeValue) -> TypeGuard[List[RuntimeValue]]:
    return isinstance(value, list)


def _is_dict(value: RuntimeValue) -> TypeGuard[Dict[str, RuntimeValue]]:
    return isinstance(value, dict)


def _ensure_json_like(value: RuntimeValue, *, path: str) -> JsonLike:
    return _ensure_json_like_ssot(
        value,
        path=path,
        value_name="Signature value",
        allowed_types_desc="None/bool/int/float/str/list/tuple/dict[str, ...]",
        dict_key_desc="str",
        require_nonempty_dict_key=False,
        error_cls=ScalimWorkflowCachePoolError,
    )


@overload
def _normalize_json_like(value: Dict[str, JsonLike]) -> Dict[str, JsonLike]: ...


@overload
def _normalize_json_like(value: List[JsonLike]) -> List[JsonLike]: ...


@overload
def _normalize_json_like(value: JsonLike) -> JsonLike: ...


@overload
def _normalize_json_like(value: RuntimeValue) -> JsonLike: ...


def _normalize_json_like(value: RuntimeValue) -> JsonLike:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if _is_list(value):
        return [_normalize_json_like(item) for item in value]
    if _is_dict(value):
        out: Dict[str, JsonLike] = {}
        for raw_key in sorted(value.keys(), key=str):
            out[str(raw_key)] = _normalize_json_like(value[raw_key])
        return out
    return cast("JsonLike", value)  # pragma: allow-cast normalize passthrough after scalar/list/dict branches


def _canonical_json_dumps(value: JsonLike) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _lookup_cast_signature(cast_spec: Optional[LookupCastSpecIr]) -> Optional[Dict[str, JsonLike]]:
    if cast_spec is None:
        return None
    name = str(cast_spec.name or "").strip() or "auto"
    payload: Dict[str, JsonLike] = {"name": name}
    if name == "sep_first":
        payload["sep"] = str(cast_spec.sep or ",")
    _ = _ensure_json_like(payload, path="(lookup_cast)")
    return _normalize_json_like(payload)  # pragma: allow-any-return signature payload json-like normalization


@dataclass(frozen=True)
class WorkflowCacheEntrySignature:
    kind: str
    source_id: str
    loader_ref: str
    rendered_params: JsonLike
    normalize: Optional[Dict[str, JsonLike]] = None
    key: JsonLike = None
    lookup_cast: Optional[Dict[str, JsonLike]] = None

    def logical_key(self) -> Tuple[str, str]:
        return (str(self.kind), str(self.source_id))

    def as_dict(self) -> Dict[str, JsonLike]:
        return {
            "kind": str(self.kind),
            "source_id": str(self.source_id),
            "loader_ref": str(self.loader_ref),
            "rendered_params": self.rendered_params,
            "normalize": self.normalize or None,
            "key": self.key,
            "lookup_cast": self.lookup_cast or None,
        }

    def canonical_key(self) -> str:
        normalized = _normalize_json_like(self.as_dict())
        return _canonical_json_dumps(normalized)

    def digest(self) -> str:
        payload = self.canonical_key().encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]


def build_preload_forever_signature(source: SourceIr, *, rendered_params: LoaderCallKwargs) -> WorkflowCacheEntrySignature:
    params_path = "sources.{}.params".format(source.source_id)
    params = _normalize_json_like(_ensure_json_like(rendered_params, path=params_path))

    normalize_dict: Optional[Dict[str, JsonLike]] = None
    if source.normalize is not None:
        norm = source.normalize
        normalize_payload: Dict[str, JsonLike] = {
            "kind": norm.kind,
            "key_field": norm.key_field,
            "on_conflict": norm.on_conflict,
            "on_empty": norm.on_empty,
            "on_missing": norm.on_missing,
            "call_by_ref": None if norm.call_by_ref is None else describe_callable_ref(norm.call_by_ref),
            "fields": [
                {
                    "name": rule.name,
                    "from_key": rule.from_key,
                    "extract_expr": rule.extract_expr,
                    "extract_segments": list(rule.extract_segments or ()),
                }
                for rule in norm.fields
            ],
        }
        _ = _ensure_json_like(normalize_payload, path="sources.{}.normalize".format(source.source_id))
        normalize_dict = _normalize_json_like(normalize_payload)

    signature = WorkflowCacheEntrySignature(
        kind="preload_forever",
        source_id=str(source.source_id),
        loader_ref=describe_callable_ref(source.loader_spec.callable_ref),
        rendered_params=params,
        normalize=normalize_dict,
        key=_normalize_json_like(_ensure_json_like(source.key.key, path="sources.{}.key".format(source.source_id))),
        lookup_cast=_lookup_cast_signature(source.key.cast),
    )
    # 校验顶层 `JSON-like` 结构.
    _ = _ensure_json_like(signature.as_dict(), path="(signature)")
    return signature


def diff_signature_fields(left: WorkflowCacheEntrySignature, right: WorkflowCacheEntrySignature) -> List[str]:
    diff: List[str] = []
    left_dict = left.as_dict()
    right_dict = right.as_dict()
    for key in sorted(left_dict.keys()):
        if left_dict.get(key) != right_dict.get(key):
            diff.append(str(key))
    return diff


@dataclass
class _CacheEntry:
    signature: WorkflowCacheEntrySignature
    value: Optional[LoaderResultMapping] = None
    loading: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class WorkflowCachePool:
    _workflow_exec_id: str
    _instrumentation: InstrumentationHub
    _conflict_policy: str
    _release_policy: str
    _max_entries: Optional[int]
    _over_budget_policy: Optional[str]
    _pinned_logical_keys: FrozenSet[Tuple[str, str]]
    _logical_keys_by_node_id: Mapping[str, FrozenSet[Tuple[str, str]]]
    _remaining_consumers_by_logical_key: Dict[Tuple[str, str], Set[str]]
    _entries: "OrderedDict[str, _CacheEntry]"
    _signature_keys_by_logical_key: Dict[Tuple[str, str], Set[str]]
    _acquired_by_node_id: Dict[str, Set[str]]
    _done_node_ids: Set[str]
    _lock: threading.Lock

    def __init__(
        self,
        *,
        workflow_exec_id: str,
        instrumentation: InstrumentationHub,
        config: WorkflowCachePoolIr,
        logical_keys_by_node_id: Mapping[str, FrozenSet[Tuple[str, str]]],
        consumers_by_logical_key: Mapping[Tuple[str, str], FrozenSet[str]],
    ) -> None:
        self._workflow_exec_id = str(workflow_exec_id)
        self._instrumentation = instrumentation
        self._conflict_policy = str(config.conflict_policy)
        self._release_policy = str(config.release_policy)
        if config.budget is None:
            self._max_entries = None
            self._over_budget_policy = None
        else:
            self._max_entries = int(config.budget.max_entries)
            self._over_budget_policy = str(config.budget.over_budget_policy)
        self._pinned_logical_keys = frozenset((str(p.kind), str(p.source_id)) for p in (config.pin or ()))

        self._logical_keys_by_node_id = {
            str(node_id): frozenset((str(kind), str(source_id)) for kind, source_id in keys)
            for node_id, keys in logical_keys_by_node_id.items()
        }
        self._remaining_consumers_by_logical_key = {
            (str(kind), str(source_id)): {str(node_id) for node_id in consumers}
            for (kind, source_id), consumers in consumers_by_logical_key.items()
        }

        self._entries = OrderedDict()
        self._signature_keys_by_logical_key = {}
        self._acquired_by_node_id = {}
        self._done_node_ids = set()
        self._lock = threading.Lock()

    def get_or_load(
        self,
        signature: WorkflowCacheEntrySignature,
        *,
        workflow_node_id: str,
        load_fn: Callable[[], LoaderResultMapping],
    ) -> LoaderResultMapping:
        node_id = str(workflow_node_id)
        logical_key = signature.logical_key()
        signature_key = signature.canonical_key()
        signature_digest = signature.digest()

        conflict_diff: Optional[List[str]] = None
        conflict_target_digest: Optional[str] = None

        pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]] = []

        with self._lock:
            existing_keys = self._signature_keys_by_logical_key.get(logical_key, set())
            if existing_keys and signature_key not in existing_keys:
                first_key = next(iter(existing_keys))
                first_entry = self._entries.get(first_key)
                if first_entry is not None:
                    conflict_diff = diff_signature_fields(first_entry.signature, signature)
                    conflict_target_digest = first_entry.signature.digest()

                if self._conflict_policy == "error":
                    msg = "cache_pool signature conflict for kind='{}', source_id='{}' (diff={})".format(
                        logical_key[0],
                        logical_key[1],
                        ",".join(conflict_diff or []),
                    )
                    raise ScalimWorkflowCachePoolError(msg, path="workflow_runtime_options.cache_pool")

                # `warn/separate`: 允许并行存在多个条目,但需要可诊断(含差异摘要).
                warn_msg = "cache_pool signature conflict for kind='{}', source_id='{}' (policy={}, diff={})".format(
                    logical_key[0],
                    logical_key[1],
                    self._conflict_policy,
                    ",".join(conflict_diff or []),
                )
                pending_emits.append(
                    (
                        EventType.DIAGNOSTIC_WARNING,
                        DiagnosticWarningEvent(
                            message=warn_msg,
                            source_id=str(logical_key[1]),
                            field_id=None,
                            lookup_key=None,
                            row_id=None,
                        ),
                        {
                            "workflow_exec_id": self._workflow_exec_id,
                            "workflow_node_id": node_id,
                        },
                    )
                )

            entry = self._entries.get(signature_key)
            cache_status = "hit" if entry is not None and entry.value is not None else "miss"
            if entry is None:
                self._ensure_budget_for_new_entry(workflow_node_id=node_id, pending_emits=pending_emits)
                entry = _CacheEntry(signature=signature, loading=True)
                self._entries[signature_key] = entry
                self._signature_keys_by_logical_key.setdefault(logical_key, set()).add(signature_key)
            elif entry.value is None:
                # 淘汰护栏: 对于缓存未命中且即将进入加载流程的调用,在释放全局锁前建立“加载中”意图标记.
                # 注意: 事件发射必须在锁外执行,这里不做任何外部回调.
                entry.loading = True

            self._acquired_by_node_id.setdefault(node_id, set()).add(signature_key)
            self._entries.move_to_end(signature_key)

            pending_emits.append(
                (
                    EventType.WORKFLOW_CACHE_ACQUIRE,
                    WorkflowCacheAcquireEvent(
                        workflow_exec_id=self._workflow_exec_id,
                        workflow_node_id=node_id,
                        cache_kind=str(logical_key[0]),
                        source_id=str(logical_key[1]),
                        signature_digest=signature_digest,
                        cache_status=cache_status,
                        conflict_policy=str(self._conflict_policy),
                        conflict_detected=bool(conflict_diff),
                        conflict_diff_fields=tuple(conflict_diff or ()),
                        conflict_target_signature_digest=conflict_target_digest,
                    ),
                    {
                        "workflow_exec_id": self._workflow_exec_id,
                        "workflow_node_id": node_id,
                    },
                )
            )

        for event_type, payload, meta in pending_emits:
            _ = self._instrumentation.emit(str(event_type), payload, meta=meta)

        # 加载过程由每条目锁(`per-entry lock`)保护.
        with entry.lock:
            if entry.value is not None:
                # 修复: 若之前在锁外已标记为“加载中”,在命中快路径返回前必须清理,避免条目永久处于“加载中”而无法淘汰.
                entry.loading = False
                return entry.value
            entry.loading = True
            try:
                loaded = load_fn()
                entry.value = loaded
                return loaded
            finally:
                entry.loading = False

    def on_workflow_node_done(self, workflow_node_id: str) -> None:
        node_id = str(workflow_node_id)

        pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]] = []

        with self._lock:
            if node_id in self._done_node_ids:
                return
            self._done_node_ids.add(node_id)

            acquired = self._acquired_by_node_id.pop(node_id, set())
            pending_emits.extend(self._collect_release_events(node_id=node_id, acquired_signature_keys=acquired))
            evict_reasons = self._collect_refcount_evictions(node_id=node_id)
            for signature_key, reason in evict_reasons.items():
                pending = self._evict_entry(signature_key, workflow_node_id=node_id, reason=reason)
                if pending is not None:
                    pending_emits.append(pending)

        for event_type, payload, meta in pending_emits:
            _ = self._instrumentation.emit(str(event_type), payload, meta=meta)

    def _collect_release_events(self, *, node_id: str, acquired_signature_keys: Set[str]) -> List[Tuple[str, RuntimeValue, Dict[str, str]]]:
        pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]] = []
        for signature_key in acquired_signature_keys:
            entry = self._entries.get(signature_key)
            if entry is None:
                continue
            logical_key = entry.signature.logical_key()
            remaining = len(self._remaining_consumers_by_logical_key.get(logical_key, set()))
            pending_emits.append(
                (
                    EventType.WORKFLOW_CACHE_RELEASE,
                    WorkflowCacheReleaseEvent(
                        workflow_exec_id=self._workflow_exec_id,
                        workflow_node_id=node_id,
                        cache_kind=str(logical_key[0]),
                        source_id=str(logical_key[1]),
                        signature_digest=entry.signature.digest(),
                        remaining_consumers=remaining,
                        release_policy=str(self._release_policy),
                        is_pinned=logical_key in self._pinned_logical_keys,
                    ),
                    {
                        "workflow_exec_id": self._workflow_exec_id,
                        "workflow_node_id": node_id,
                    },
                )
            )
        return pending_emits

    def _collect_refcount_evictions(self, *, node_id: str) -> Dict[str, str]:
        evict_reasons: Dict[str, str] = {}
        for logical_key in self._logical_keys_by_node_id.get(node_id, frozenset()):
            remaining = self._remaining_consumers_by_logical_key.get(logical_key)
            if remaining is None:
                continue
            remaining.discard(node_id)
            if remaining:
                continue
            if self._release_policy != "dag_refcount":
                continue
            if logical_key in self._pinned_logical_keys:
                continue
            for signature_key in list(self._signature_keys_by_logical_key.get(logical_key, set())):
                entry = self._entries.get(signature_key)
                if entry is not None and entry.loading:
                    continue
                evict_reasons[signature_key] = "refcount_zero"
        return evict_reasons

    def close(self) -> None:
        with self._lock:
            loading_entries = [e for e in self._entries.values() if e.loading]

        for entry in loading_entries:
            with entry.lock:
                pass

        pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]] = []
        with self._lock:
            for signature_key in list(self._entries.keys()):
                pending = self._evict_entry(signature_key, workflow_node_id="workflow_end", reason="workflow_end")
                if pending is not None:
                    pending_emits.append(pending)

        for event_type, payload, meta in pending_emits:
            _ = self._instrumentation.emit(str(event_type), payload, meta=meta)

    def _ensure_budget_for_new_entry(self, *, workflow_node_id: str, pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]]) -> None:
        max_entries = self._max_entries
        if max_entries is None:
            return
        if max_entries < 1:  # pragma: no cover  # pragma: allow-no-cover invariant: budget validated by config loader
            msg = "cache_pool budget.max_entries must be >= 1"
            raise ScalimWorkflowCachePoolError(msg, path="workflow_runtime_options.cache_pool.max_entries")
        if len(self._entries) < max_entries:
            return

        if self._over_budget_policy == "fail_fast":
            msg = "cache_pool over budget: max_entries={} (over_budget_policy=fail_fast)".format(max_entries)
            raise ScalimWorkflowCachePoolError(msg, path="workflow_runtime_options.cache_pool")

        if self._over_budget_policy != "evict_lru":
            msg = "cache_pool over_budget_policy '{}' is not supported".format(self._over_budget_policy)
            raise ScalimWorkflowCachePoolError(msg, path="workflow_runtime_options.cache_pool")

        evicted = self._evict_lru_idle(workflow_node_id=workflow_node_id, pending_emits=pending_emits)
        if not evicted:
            msg = "cache_pool over budget: max_entries={} (no evictable refcount=0 entries)".format(max_entries)
            raise ScalimWorkflowCachePoolError(msg, path="workflow_runtime_options.cache_pool")

    def _evict_lru_idle(self, *, workflow_node_id: str, pending_emits: List[Tuple[str, RuntimeValue, Dict[str, str]]]) -> bool:
        for signature_key, entry in list(self._entries.items()):
            logical_key = entry.signature.logical_key()
            if logical_key in self._pinned_logical_keys:
                continue
            if entry.loading:
                continue
            remaining = self._remaining_consumers_by_logical_key.get(logical_key, set())
            if remaining:
                continue
            pending = self._evict_entry(signature_key, workflow_node_id=workflow_node_id, reason="budget_lru")
            if pending is not None:
                pending_emits.append(pending)
            return True
        return False

    def _evict_entry(
        self,
        signature_key: str,
        *,
        workflow_node_id: str,
        reason: str,
    ) -> Optional[Tuple[str, RuntimeValue, Dict[str, str]]]:
        entry = self._entries.pop(signature_key, None)
        if entry is None:
            return None
        logical_key = entry.signature.logical_key()
        keys = self._signature_keys_by_logical_key.get(logical_key)
        if keys is not None:
            keys.discard(signature_key)
            if not keys:
                _ = self._signature_keys_by_logical_key.pop(logical_key, None)
                _ = self._remaining_consumers_by_logical_key.pop(logical_key, None)

        return (
            EventType.WORKFLOW_CACHE_EVICT,
            WorkflowCacheEvictEvent(
                workflow_exec_id=self._workflow_exec_id,
                workflow_node_id=str(workflow_node_id),
                cache_kind=str(logical_key[0]),
                source_id=str(logical_key[1]),
                signature_digest=entry.signature.digest(),
                reason=str(reason),
            ),
            {
                "workflow_exec_id": self._workflow_exec_id,
                "workflow_node_id": str(workflow_node_id),
            },
        )


__all__ = (
    "ScalimWorkflowCachePoolError",
    "WorkflowCacheEntrySignature",
    "WorkflowCachePool",
    "build_preload_forever_signature",
    "diff_signature_fields",
)
