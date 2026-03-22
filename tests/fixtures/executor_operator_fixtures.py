from typing import Any, Dict, List, Optional

from scalim.execution.guardrails import GuardrailsPolicy
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.hooks.base import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.sources import MainSourceIr


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
    return MainSourceIr(source_id=source_id, loader=lambda: [])


def _raise_value_error(_value):  # type: ignore[no-untyped-def]
    raise ValueError("bad")


def _raise_type_error(_value):  # type: ignore[no-untyped-def]
    raise TypeError("bad")


def _make_runtime(
    plan: ExecutionPlan,
    main_source: Optional[MainSourceIr],
    hook_manager: Optional[HookManager] = None,
    observer_manager: Optional[ObserverManager] = None,
    guardrails: Optional[GuardrailsPolicy] = None,
    key_normalization: str = "raw",
) -> ExecutionRuntime:
    hook_manager = hook_manager or HookManager()
    observer_manager = observer_manager or ObserverManager()
    return ExecutionRuntime(plan, hook_manager, observer_manager, main_source, guardrails=guardrails, key_normalization=key_normalization)  # type: ignore[arg-type]


class _WantsInstrumentation(object):
    def __init__(self, wanted_event_type: str) -> None:
        self._wanted_event_type = wanted_event_type
        self.loader_slim_calls = []

    def wants(self, event_type: str) -> bool:
        return event_type == self._wanted_event_type

    def emit_loader_slim(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.loader_slim_calls.append(kwargs)


class _Runtime(object):
    def __init__(self, instrumentation: _WantsInstrumentation, batch_num: int = 1) -> None:
        self.instrumentation = instrumentation
        self.batch_num = batch_num


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
