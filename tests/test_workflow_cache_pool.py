import math
import threading
from types import SimpleNamespace

import pytest

from scalim.execution.pipeline.base.pipeline import Pipeline
from scalim.execution.workflow_cache_pool import WorkflowCacheEntrySignature, WorkflowCachePool, ScalimWorkflowCachePoolError
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from scalim.spec.ir.workflow import WorkflowCachePoolBudgetIr, WorkflowCachePoolIr, WorkflowCachePoolPinIr
from scalim.typedefs import SourceSpecIrCacheMode

_TIMEOUT_S = 5.0


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
    from scalim.utils.json_like import ensure_json_like

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
    from scalim.spec.ir.sources import SourceNormalizeIr

    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable=lambda: {}),
        normalize=SourceNormalizeIr(kind="index_by_key", key_field="id"),
    )

    signature = mod.build_preload_forever_signature(source, rendered_params={})  # type: ignore[arg-type]
    assert signature.normalize is not None
    assert signature.normalize.get("kind") == "index_by_key"
    assert signature.normalize.get("key_field") == "id"


def test_format_callable_reference_and_lookup_cast_signature_variants() -> None:
    from scalim.execution import workflow_cache_pool as mod

    assert mod._format_callable_reference(len) == "len"  # type: ignore[attr-defined]
    expected = "{}:{}".format(_TopLevelCallable.method.__module__, _TopLevelCallable.method.__qualname__)
    assert mod._format_callable_reference(_TopLevelCallable.method) == expected  # type: ignore[attr-defined]
    assert mod._format_callable_reference(SimpleNamespace(__module__="m", __qualname__="", __name__="")) == "m"  # type: ignore[attr-defined]

    cast_fn = SimpleNamespace(
        scalim_lookup_cast_name="id_cast",
        scalim_lookup_cast_meta={
            "name": "ignored",
            "answer": 42,
        },
    )
    assert mod._lookup_cast_signature(cast_fn) == {"name": "id_cast", "answer": 42}  # type: ignore[attr-defined]

    fallback = mod._lookup_cast_signature(lambda x: x)  # type: ignore[attr-defined]
    assert fallback is not None
    assert "callable" in fallback


class _TopLevelCallable(object):
    def method(self) -> None:
        return None


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
        loader_spec=LoaderIr(callable=lambda: {1: {"id": 1, "value": "ok"}}),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    plan = ExecutionPlan(preload_sources=(source,))
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = _make_runtime(plan, hook_manager=hook_manager, observer_manager=observer_manager, cache=cache)
    executor = _make_executor(plan, runtime)
    pipeline = _TestPipeline(
        plan,
        executor,
        runtime,
        hook_manager,
        observer_manager,
        DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader=lambda: [])),
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
        loader_spec=LoaderIr(callable=lambda: {1: {"id": 1, "value": "ok"}}),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    plan = ExecutionPlan(preload_sources=(source,))
    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = _make_runtime(plan, hook_manager=hook_manager, observer_manager=observer_manager, cache=cache)
    executor = _make_executor(plan, runtime)
    pipeline = _TestPipeline(
        plan,
        executor,
        runtime,
        hook_manager,
        observer_manager,
        DemandIr(sources={}, fields={}, main_source=MainSourceIr(source_id="main", loader=lambda: [])),
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
):
    from scalim.execution.executor.runtime.runtime import ExecutionRuntime

    return ExecutionRuntime(
        plan,
        hook_manager,
        observer_manager,
        MainSourceIr(source_id="main", loader=lambda: []),
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
    logical_keys_by_node_id=None,
    consumers_by_logical_key=None,
):
    from scalim.ob.hub import InstrumentationHub

    instrumentation = InstrumentationHub(hook_manager=HookManager(), observer_manager=ObserverManager())
    return WorkflowCachePool(
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
        loader_ref="tests.loader",
        rendered_params={"k": str(source_id)},
        normalize=None,
        key=None,
        lookup_cast=None,
    )


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
        if not allow_finish.wait(timeout=_TIMEOUT_S):
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
    if not load_started.wait(timeout=_TIMEOUT_S):
        pytest.fail("load_fn did not start")

    t2 = threading.Thread(
        target=_worker2,
        daemon=True,
    )
    t2.start()
    if not thread2_started.wait(timeout=_TIMEOUT_S):
        pytest.fail("thread2 did not start")
    if thread2_done.wait(timeout=0.1):
        pytest.fail("thread2 finished before load finished; expected in-flight wait")

    allow_finish.set()

    if not thread1_done.wait(timeout=_TIMEOUT_S):
        pytest.fail("thread1 did not finish")
    if not thread2_done.wait(timeout=_TIMEOUT_S):
        pytest.fail("thread2 did not finish")

    t1.join(timeout=_TIMEOUT_S)
    t2.join(timeout=_TIMEOUT_S)
    if t1.is_alive() or t2.is_alive():
        pytest.fail("threads did not finish")

    assert not errors
    assert len(calls) == 1
    assert len(results) == 2
    assert results[0] == {1: {"id": 1}}
    assert results[1] == {1: {"id": 1}}


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
    if not runner_done.wait(timeout=_TIMEOUT_S):
        pytest.fail("WorkflowCachePool.emit appears to be called under internal locks (reentry deadlock)")
