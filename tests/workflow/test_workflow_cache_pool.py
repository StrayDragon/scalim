import math
import threading

import pytest

from scalim.execution.pipeline.base.pipeline import Pipeline
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.workflow_cache_pool import WorkflowCacheEntrySignature, WorkflowCachePool, ScalimWorkflowCachePoolError
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr
from scalim.spec.ir._workflow import WorkflowCachePoolBudgetIr, WorkflowCachePoolIr, WorkflowCachePoolPinIr
from scalim.typedefs import SourceSpecIrCacheMode

from tests.support.testing_utils import CI_TIMEOUT_S, NEGATIVE_TIMEOUT_S, event_wait, join_or_fail


def test_json_like_helpers_reject_invalid_values() -> None:
    from scalim.execution import workflow_cache_pool as mod

    assert mod._ensure_json_like(1.5, path="x") == 1.5  # type: ignore[attr-defined]

    with pytest.raises(ScalimWorkflowCachePoolError, match="float must be finite"):
        _ = mod._ensure_json_like(math.nan, path="x")  # type: ignore[attr-defined]

    with pytest.raises(ScalimWorkflowCachePoolError, match="dict key must be str"):
        _ = mod._ensure_json_like({1: "x"}, path="x")  # type: ignore[attr-defined]

    with pytest.raises(ScalimWorkflowCachePoolError, match="must be JSON-like"):
        _ = mod._ensure_json_like(set([1]), path="x")  # type: ignore[attr-defined]

    payload = mod._normalize_json_like((1, 2))  # type: ignore[attr-defined]
    assert payload == (1, 2)


def test_ensure_json_like_rejects_empty_dict_key_when_required() -> None:
    from scalim._internal.utils.json_like import ensure_json_like

    with pytest.raises(ScalimWorkflowCachePoolError, match="dict key must be str"):
        _ = ensure_json_like(
            {"": 1},
            path="x",
            value_name="value",
            allowed_types_desc="dict[str, ...]",
            dict_key_desc="str",
            require_nonempty_dict_key=True,
            error_cls=ScalimWorkflowCachePoolError,
        )


def test_build_preload_forever_signature_normalizes_normalize_payload() -> None:
    from scalim.execution import workflow_cache_pool as mod
    from scalim.spec.ir import SourceNormalizeIr

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="s1.loader")),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="id"),
    )

    signature = mod.build_preload_forever_signature(source, rendered_params={})  # type: ignore[arg-type]
    assert signature.loader_ref == "runtime:s1.loader"
    assert signature.normalize is not None
    assert signature.normalize.get("kind") == "index_by_key"
    assert signature.normalize.get("key_field") == "id"


def test_lookup_cast_signature_variants() -> None:
    from scalim.execution import workflow_cache_pool as mod
    from scalim.spec.ir.lookup_casts import LookupCastSpecIr

    assert mod._lookup_cast_signature(None) is None  # type: ignore[arg-type]
    assert mod._lookup_cast_signature(LookupCastSpecIr(name="id_cast")) == {"name": "id_cast"}  # type: ignore[attr-defined]
    assert mod._lookup_cast_signature(LookupCastSpecIr(name="sep_first")) == {"name": "sep_first", "sep": ","}  # type: ignore[attr-defined]
    assert mod._lookup_cast_signature(LookupCastSpecIr(name="sep_first", sep="|")) == {"name": "sep_first", "sep": "|"}  # type: ignore[attr-defined]


def test_workflow_cache_pool_release_and_refcount_edge_cases() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="dag_refcount",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={"n1": frozenset([("preload_forever", "s1")])},
        consumers_by_logical_key={},
    )

    pool.on_workflow_node_done("n1")
    pool.on_workflow_node_done("n1")

    _ = pool._collect_release_events(node_id="n2", acquired_signature_keys=set(["missing"]))  # type: ignore[attr-defined]


def test_workflow_cache_pool_budget_rejects_unknown_policy() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="nope"),
        ),
    )
    _ = pool.get_or_load(_sig("s1"), workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    with pytest.raises(ScalimWorkflowCachePoolError, match="over_budget_policy"):
        _ = pool.get_or_load(_sig("s2"), workflow_node_id="n2", load_fn=lambda: {1: {"id": 1}})


def test_workflow_cache_pool_budget_evict_lru_fails_when_pinned_and_no_evictable_entry() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="evict_lru"),
            pin=(WorkflowCachePoolPinIr(kind="preload_forever", source_id="s1"),),
        ),
    )
    _ = pool.get_or_load(_sig("s1"), workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    with pytest.raises(ScalimWorkflowCachePoolError, match="no evictable"):
        _ = pool.get_or_load(_sig("s2"), workflow_node_id="n2", load_fn=lambda: {1: {"id": 1}})


def test_workflow_cache_pool_evict_lru_skips_loading_and_remaining_consumers() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="evict_lru"),
        ),
    )
    signature = _sig("s1")
    _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    entry = pool._entries[signature.canonical_key()]  # type: ignore[attr-defined]
    entry.loading = True
    assert pool._evict_lru_idle(workflow_node_id="n2", pending_emits=[]) is False  # type: ignore[attr-defined]
    entry.loading = False

    pool._remaining_consumers_by_logical_key[signature.logical_key()] = set(["n1"])  # type: ignore[attr-defined]
    assert pool._evict_lru_idle(workflow_node_id="n2", pending_emits=[]) is False  # type: ignore[attr-defined]


def test_workflow_cache_pool_evict_lru_appends_pending_emits_cover_branch() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )
    signature = _sig("s1")
    _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    pending_emits = []
    assert pool._evict_lru_idle(workflow_node_id="n2", pending_emits=pending_emits) is True  # type: ignore[attr-defined]
    assert len(pending_emits) == 1
    assert signature.canonical_key() not in pool._entries  # type: ignore[attr-defined]


def test_workflow_cache_pool_evict_entry_keeps_logical_key_index_when_other_entries_remain_cover_branch() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )

    signature1 = _sig("s1")
    signature2 = WorkflowCacheEntrySignature(
        kind=signature1.kind,
        source_id=signature1.source_id,
        loader_ref=signature1.loader_ref,
        rendered_params={"k": "s2"},
        normalize=None,
        key=None,
        lookup_cast=None,
    )

    _ = pool.get_or_load(signature1, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})
    _ = pool.get_or_load(signature2, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    logical_key = signature1.logical_key()
    signature1_key = signature1.canonical_key()
    signature2_key = signature2.canonical_key()
    assert signature1_key != signature2_key

    _ = pool._evict_entry(signature1_key, workflow_node_id="n2", reason="x")  # type: ignore[attr-defined]

    remaining = pool._signature_keys_by_logical_key.get(logical_key)  # type: ignore[attr-defined]
    assert remaining == set([signature2_key])


def test_workflow_cache_pool_collect_refcount_evictions_skips_loading_entries() -> None:
    signature = _sig("s1")
    logical_key = signature.logical_key()
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="dag_refcount",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={"n1": frozenset([logical_key])},
        consumers_by_logical_key={logical_key: set(["n1"])},
    )
    _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    entry = pool._entries[signature.canonical_key()]  # type: ignore[attr-defined]
    entry.loading = True
    assert pool._collect_refcount_evictions(node_id="n1") == {}  # type: ignore[attr-defined]

    pool._evict_entry("missing", workflow_node_id="n3", reason="x")  # type: ignore[attr-defined]


def test_workflow_cache_pool_collect_refcount_evictions_skips_when_release_policy_not_refcount() -> None:
    signature = _sig("s1")
    logical_key = signature.logical_key()
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={"n1": frozenset([logical_key])},
        consumers_by_logical_key={logical_key: set(["n1"])},
    )

    assert pool._collect_refcount_evictions(node_id="n1") == {}  # type: ignore[attr-defined]


def test_workflow_cache_pool_budget_disabled_skips_over_budget_and_refcount_release() -> None:
    signature = _sig("s1")
    logical_key = signature.logical_key()
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=None,
        ),
        logical_keys_by_node_id={"n1": frozenset([logical_key])},
        consumers_by_logical_key={logical_key: set(["n1"])},
    )
    _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})
    pool.on_workflow_node_done("n1")
    assert signature.canonical_key() in pool._entries  # type: ignore[attr-defined]

    _ = pool.get_or_load(_sig("s2"), workflow_node_id="n2", load_fn=lambda: {1: {"id": 1}})
    pool.close()
    assert signature.canonical_key() not in pool._entries  # type: ignore[attr-defined]


def test_workflow_cache_pool_collect_refcount_evictions_skips_pinned_logical_key() -> None:
    signature = _sig("s1")
    logical_key = signature.logical_key()
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="dag_refcount",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
            pin=(WorkflowCachePoolPinIr(kind="preload_forever", source_id="s1"),),
        ),
        logical_keys_by_node_id={"n1": frozenset([logical_key])},
        consumers_by_logical_key={logical_key: set(["n1"])},
    )

    assert pool._collect_refcount_evictions(node_id="n1") == {}  # type: ignore[attr-defined]


def test_workflow_cache_pool_close_waits_for_loading_entry_lock() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )
    signature = _sig("s1")
    _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}})

    entry = pool._entries[signature.canonical_key()]  # type: ignore[attr-defined]
    entry.loading = True

    pool.close()


def test_pipeline_preload_uses_preloaded_cache_get_or_load() -> None:
    class _PreloadedCache(dict):
        def __init__(self) -> None:
            super(_PreloadedCache, self).__init__()
            self.calls = []

        def get_or_load(self, source_id, load_fn):  # type: ignore[no-untyped-def]
            self.calls.append(source_id)
            return load_fn()

    cache = _PreloadedCache()
    source = SourceIr(
        source_id="preload",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="preload.loader")),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    plan = ExecutionPlan(preload_sources=(source,))
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": lambda: []},
        source_loaders={"preload": lambda: {1: {"id": 1, "value": "ok"}}},
    )
    runtime = _make_runtime(
        plan,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        cache=cache,
        sources={"preload": source},
        runtime_bindings=runtime_bindings,
    )
    executor = _make_executor(plan, runtime)
    pipeline = _TestPipeline(
        plan,
        executor,
        runtime,
        hook_manager,
        observer_manager,
        DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))),
    )

    pipeline._preload_cached_sources()  # type: ignore[attr-defined]
    assert cache.calls == ["preload"]
    assert "preload" in cache


def test_pipeline_preload_passes_signature_digest_when_guardrail_enabled() -> None:
    class _PreloadedCache(dict):
        signature_guardrail_enabled = True

        def __init__(self) -> None:
            super(_PreloadedCache, self).__init__()
            self.calls = []

        def get_or_load(self, source_id, load_fn, *, signature_digest=None):  # type: ignore[no-untyped-def]
            assert signature_digest
            self.calls.append((source_id, str(signature_digest)))
            return load_fn()

    cache = _PreloadedCache()
    source = SourceIr(
        source_id="preload",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="preload.loader")),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    plan = ExecutionPlan(preload_sources=(source,))
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": lambda: []},
        source_loaders={"preload": lambda: {1: {"id": 1, "value": "ok"}}},
    )
    runtime = _make_runtime(
        plan,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        cache=cache,
        sources={"preload": source},
        runtime_bindings=runtime_bindings,
    )
    executor = _make_executor(plan, runtime)
    pipeline = _TestPipeline(
        plan,
        executor,
        runtime,
        hook_manager,
        observer_manager,
        DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader"))),
    )

    pipeline._preload_cached_sources()  # type: ignore[attr-defined]
    assert [item[0] for item in cache.calls] == ["preload"]
    assert cache.calls[0][1]
    assert "preload" in cache


class _TestPipeline(Pipeline):
    def run(self, main_rows=None, sink=None):  # type: ignore[no-untyped-def]
        _ = main_rows, sink
        return []


def _make_runtime(  # type: ignore[no-untyped-def]
    plan,
    *,
    hook_manager,
    observer_manager,
    cache,
    sources,
    runtime_bindings,
):
    from scalim.execution.executor.runtime.runtime import ExecutionRuntime

    return ExecutionRuntime(
        plan,
        hook_manager,
        observer_manager,
        MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources,
        runtime_bindings,
        preloaded_cache=cache,
        workflow_cache_pool=None,
        workflow_node_id=None,
    )


def _make_executor(plan, runtime):  # type: ignore[no-untyped-def]
    from scalim.execution.executor.batch.executor import BatchExecutor

    return BatchExecutor(plan, runtime)


def _make_pool(  # type: ignore[no-untyped-def]
    *,
    config,
    pool_cls=WorkflowCachePool,
    logical_keys_by_node_id=None,
    consumers_by_logical_key=None,
):
    from scalim.ob.hub import InstrumentationHub

    instrumentation = InstrumentationHub(hook_manager=HookManager(), observer_manager=ObserverManager())
    return pool_cls(
        workflow_exec_id="wf",
        instrumentation=instrumentation,
        config=config,
        logical_keys_by_node_id=logical_keys_by_node_id or {},
        consumers_by_logical_key=consumers_by_logical_key or {},
    )


def _sig(source_id: str) -> WorkflowCacheEntrySignature:
    return WorkflowCacheEntrySignature(
        kind="preload_forever",
        source_id=str(source_id),
        loader_ref="tests.fixtures.workflow_loaders:load_main_fast",
        rendered_params={"k": str(source_id)},
        normalize=None,
        key=None,
        lookup_cast=None,
    )


class _DropPendingEvictPool(WorkflowCachePool):
    def _evict_entry(self, signature_key: str, *, workflow_node_id: str, reason: str):  # type: ignore[no-untyped-def]
        _ = super()._evict_entry(signature_key, workflow_node_id=workflow_node_id, reason=reason)  # noqa: SLF001
        return None


def test_workflow_cache_pool_get_or_load_dedupes_concurrent_loads_per_signature() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )
    signature = _sig("s1")

    load_started = threading.Event()
    allow_finish = threading.Event()
    thread2_started = threading.Event()
    thread2_done = threading.Event()
    thread1_done = threading.Event()

    calls = []

    results = []
    errors = []

    def load_fn():  # type: ignore[no-untyped-def]
        calls.append("load")
        load_started.set()
        if not allow_finish.wait(timeout=CI_TIMEOUT_S):
            pytest.fail("test fixture deadlock: allow_finish not set")
        return {1: {"id": 1}}

    def _worker1() -> None:
        try:
            results.append(pool.get_or_load(signature, workflow_node_id="n1", load_fn=load_fn))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            thread1_done.set()

    def _worker2() -> None:
        thread2_started.set()
        try:
            results.append(pool.get_or_load(signature, workflow_node_id="n2", load_fn=load_fn))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            thread2_done.set()

    t1 = threading.Thread(target=_worker1, daemon=True)
    t1.start()
    if not load_started.wait(timeout=CI_TIMEOUT_S):
        pytest.fail("load_fn did not start")

    t2 = threading.Thread(
        target=_worker2,
        daemon=True,
    )
    t2.start()
    if not thread2_started.wait(timeout=CI_TIMEOUT_S):
        pytest.fail("thread2 did not start")
    if thread2_done.wait(timeout=NEGATIVE_TIMEOUT_S):
        pytest.fail("thread2 finished before load finished; expected in-flight wait")

    allow_finish.set()

    event_wait(thread1_done, label="thread1_done")
    event_wait(thread2_done, label="thread2_done")

    join_or_fail(t1, label="cache_pool_inflight_t1")
    join_or_fail(t2, label="cache_pool_inflight_t2")

    assert not errors
    assert len(calls) == 1
    assert len(results) == 2
    assert results[0] == {1: {"id": 1}}
    assert results[1] == {1: {"id": 1}}


def test_workflow_cache_pool_retry_miss_sets_loading_intent_before_eviction_window() -> None:
    class _BlockingInstrumentation:
        def __init__(self) -> None:
            self.block_node_id = "n_retry"
            self.entered = threading.Event()
            self.allow_continue = threading.Event()

        def emit(self, event_type: str, payload, meta=None):  # type: ignore[no-untyped-def]
            _ = event_type, payload
            if not isinstance(meta, dict):
                return None
            if str(meta.get("workflow_node_id")) != self.block_node_id:
                return None
            self.entered.set()
            if not self.allow_continue.wait(timeout=CI_TIMEOUT_S):
                raise RuntimeError("test timeout waiting to continue emit")
            return None

    instrumentation = _BlockingInstrumentation()
    pool = WorkflowCachePool(
        workflow_exec_id="wf",
        instrumentation=instrumentation,  # type: ignore[arg-type]
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={},
        consumers_by_logical_key={},
    )
    signature = _sig("s1")

    def _failing_load() -> object:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _ = pool.get_or_load(signature, workflow_node_id="n1", load_fn=_failing_load)  # type: ignore[arg-type]

    retry_results = []
    retry_errors = []

    def _retry() -> None:
        try:
            retry_results.append(pool.get_or_load(signature, workflow_node_id="n_retry", load_fn=lambda: {1: {"id": 1}}))
        except Exception as exc:  # noqa: BLE001
            retry_errors.append(exc)

    t = threading.Thread(target=_retry, daemon=True)
    t.start()
    assert instrumentation.entered.wait(timeout=CI_TIMEOUT_S)

    with pytest.raises(ScalimWorkflowCachePoolError, match="no evictable"):
        _ = pool.get_or_load(_sig("s2"), workflow_node_id="n2", load_fn=lambda: {2: {"id": 2}})

    instrumentation.allow_continue.set()
    join_or_fail(t, label="cache_pool_eviction_blocked_t")
    assert not retry_errors
    assert retry_results == [{1: {"id": 1}}]

    hit_calls = []

    def _should_not_load() -> object:
        hit_calls.append("load")
        return {1: {"id": 999}}

    assert pool.get_or_load(signature, workflow_node_id="n3", load_fn=_should_not_load) == {1: {"id": 1}}
    assert hit_calls == []


def test_workflow_cache_pool_emit_does_not_deadlock_on_reentry() -> None:
    class _ReentrantInstrumentation:
        def __init__(self) -> None:
            self._reentered = False
            self.pool = None

        def emit(self, event_type: str, payload, meta=None):  # type: ignore[no-untyped-def]
            _ = event_type, payload, meta
            if self._reentered:
                return None
            self._reentered = True
            _ = self.pool.get_or_load(_sig("inner"), workflow_node_id="n_inner", load_fn=lambda: {1: {"id": 1}})  # type: ignore[union-attr]
            return None

    instrumentation = _ReentrantInstrumentation()
    pool = WorkflowCachePool(
        workflow_exec_id="wf",
        instrumentation=instrumentation,  # type: ignore[arg-type]
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={},
        consumers_by_logical_key={},
    )
    instrumentation.pool = pool

    runner_done = threading.Event()

    def _run() -> None:
        try:
            _ = pool.get_or_load(_sig("outer"), workflow_node_id="n_outer", load_fn=lambda: {1: {"id": 1}})
        finally:
            runner_done.set()

    runner = threading.Thread(
        target=_run,
        daemon=True,
    )
    runner.start()
    if not runner_done.wait(timeout=CI_TIMEOUT_S):
        pytest.fail("WorkflowCachePool.emit appears to be called under internal locks (reentry deadlock)")


def test_workflow_cache_pool_signature_conflict_with_missing_first_entry_still_loads() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )
    stale = _sig("s1")
    logical_key = stale.logical_key()
    pool._signature_keys_by_logical_key[logical_key] = set([stale.canonical_key()])  # type: ignore[attr-defined]

    signature = WorkflowCacheEntrySignature(
        kind="preload_forever",
        source_id="s1",
        loader_ref="tests.fixtures.workflow_loaders:load_main_slow",
        rendered_params={"k": "s1"},
        normalize=None,
        key=None,
        lookup_cast=None,
    )

    assert pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}}) == {1: {"id": 1}}


def test_workflow_cache_pool_on_node_done_skips_missing_eviction_pending() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="dag_refcount",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        logical_keys_by_node_id={"n1": frozenset([("preload_forever", "s1")])},
        consumers_by_logical_key={("preload_forever", "s1"): set(["n1"])},
    )

    signature = _sig("s1")
    pool._signature_keys_by_logical_key[signature.logical_key()] = set([signature.canonical_key()])  # type: ignore[attr-defined]

    pool.on_workflow_node_done("n1")


def test_workflow_cache_pool_close_skips_none_pending_from_evict_entry() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
        pool_cls=_DropPendingEvictPool,
    )
    signature = _sig("s1")
    assert pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}}) == {1: {"id": 1}}
    pool.close()


def test_workflow_cache_pool_budget_evict_lru_skips_none_pending() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=1, over_budget_policy="evict_lru"),
        ),
        pool_cls=_DropPendingEvictPool,
    )
    assert pool.get_or_load(_sig("s1"), workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}}) == {1: {"id": 1}}

    assert pool.get_or_load(_sig("s2"), workflow_node_id="n2", load_fn=lambda: {2: {"id": 2}}) == {2: {"id": 2}}


def test_workflow_cache_pool_evict_entry_skips_cleanup_when_signature_key_map_missing() -> None:
    pool = _make_pool(
        config=WorkflowCachePoolIr(
            conflict_policy="warn",
            release_policy="workflow_end",
            budget=WorkflowCachePoolBudgetIr(max_entries=10, over_budget_policy="evict_lru"),
        ),
    )
    signature = _sig("s1")
    assert pool.get_or_load(signature, workflow_node_id="n1", load_fn=lambda: {1: {"id": 1}}) == {1: {"id": 1}}

    logical_key = signature.logical_key()
    signature_key = signature.canonical_key()
    _ = pool._signature_keys_by_logical_key.pop(logical_key, None)  # type: ignore[attr-defined]

    pending = pool._evict_entry(signature_key, workflow_node_id="n1", reason="test")  # type: ignore[attr-defined]
    assert pending is not None
