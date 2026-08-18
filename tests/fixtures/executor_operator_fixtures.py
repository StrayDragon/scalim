from typing import Any, Dict, List, Optional

from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.execution.chunk_parallelism import LookupChunkParallelismPolicy
from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import MainSourceIr, RuntimeHandleIdIr


class _CaptureHook(BaseHook):
    def __init__(self) -> None:
        self.errors: List[object] = []
        self.field_computed: List[object] = []
        self.column_writes: List[object] = []
        self.field_slims: List[object] = []
        self.row_writes: List[object] = []

    def on_error(self, event) -> None:  # type: ignore[override]
        self.errors.append(event)

    def on_field_compute(self, event) -> None:  # type: ignore[override]
        self.field_computed.append(event)

    def on_column_write(self, event) -> None:  # type: ignore[override]
        self.column_writes.append(event)

    def on_field_slim(self, event) -> None:  # type: ignore[override]
        self.field_slims.append(event)

    def on_row_write(self, event) -> None:  # type: ignore[override]
        self.row_writes.append(event)


class _SampleLoader(object):
    def __init__(self) -> None:
        self.calls = 0
        self.data: Dict[int, Dict[str, Any]] = {
            1: {"order_id": 1, "amount": 10, "extra": "x"},
            2: {"order_id": 2, "amount": 20, "extra": "y"},
        }

    def get_orders(self, order_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        self.calls += 1
        return {key: value for key, value in self.data.items() if key in order_ids}


class _FailLoader(object):
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *args, **kwargs) -> Dict[Any, Any]:  # type: ignore[no-untyped-def]
        self.calls += 1
        raise AssertionError("loader should not be called")


class _Order(object):
    def __init__(self, amount: int) -> None:
        self.amount = amount


class _Target(object):
    def __init__(self, name: str) -> None:
        self.name = name


def _make_main_source(source_id: str = "orders") -> MainSourceIr:
    return MainSourceIr(source_id=source_id, loader_ref=RuntimeHandleIdIr("main_source:{}".format(source_id)))


def _raise_value_error(_value):  # type: ignore[no-untyped-def]
    raise ValueError("bad")


def _raise_type_error(_value):  # type: ignore[no-untyped-def]
    raise TypeError("bad")


TEST_SOURCE_CATALOG: Dict[str, object] = {}


def _make_runtime(
    plan: ExecutionPlan,
    main_source: Optional[MainSourceIr],
    hook_manager: Optional[HookManager] = None,
    observer_manager: Optional[ObserverManager] = None,
    sources: Optional[Dict[str, object]] = None,
    runtime_bindings: Optional[RuntimeBindings] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    key_normalization: str = "raw",
    parallel_mode: str = "seq",
    max_workers: int = 0,
    parallelize_lookup_chunks: bool = False,
    max_chunk_workers: Optional[int] = None,
) -> ExecutionRuntime:
    hook_manager = hook_manager or HookManager()
    observer_manager = observer_manager or ObserverManager()
    runtime_bindings = runtime_bindings or RuntimeBindings()
    if main_source is not None and str(main_source.source_id) not in runtime_bindings.main_source_loaders:
        runtime_bindings.main_source_loaders[str(main_source.source_id)] = lambda: []

    typed_sources = dict(TEST_SOURCE_CATALOG)
    typed_sources.update(sources or {})
    return ExecutionRuntime(
        plan=plan,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        main_source=main_source,
        sources=typed_sources,  # type: ignore[arg-type]
        runtime_bindings=runtime_bindings,
        guardrails=guardrails,
        key_normalization=key_normalization,
        parallel_mode=parallel_mode,  # type: ignore[arg-type]
        max_workers=max_workers,
        chunk_parallelism=LookupChunkParallelismPolicy(
            parallelize_lookup_chunks=parallelize_lookup_chunks,
            max_chunk_workers=max_chunk_workers,
        ),
    )


class _WantsInstrumentation(object):
    def __init__(self, wanted_event_type: str) -> None:
        self._wanted_event_type = wanted_event_type
        self.loader_slim_calls = []

    def wants(self, event_type: str) -> bool:
        return event_type == self._wanted_event_type

    def emit_loader_slim(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.loader_slim_calls.append(kwargs)


class _Runtime(object):
    def __init__(
        self,
        instrumentation: _WantsInstrumentation,
        batch_num: int = 1,
        runtime_bindings: Optional[RuntimeBindings] = None,
    ) -> None:
        self.instrumentation = instrumentation
        self.batch_num = batch_num
        self.runtime_bindings = runtime_bindings or RuntimeBindings()


__all__ = [
    "_CaptureHook",
    "_FailLoader",
    "_Order",
    "_Runtime",
    "_SampleLoader",
    "_Target",
    "_WantsInstrumentation",
    "_make_main_source",
    "_make_runtime",
    "_raise_type_error",
    "_raise_value_error",
]
