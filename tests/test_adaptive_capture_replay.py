import threading
import time
from typing import Any, Dict, List, Set

import pytest

from scalim.events import EVENT_BATCH_START, EVENT_LOADER_CALL
from scalim.events._events import BatchStartEvent
from scalim.execution.adaptive.capture import HookCaptureManager
from scalim.execution import ScalimEngine
from scalim.hooks import BaseHook, HookManager
from scalim.planning import PlanBuilder
from scalim.planning.operators import LoadRefOperatorIr
from scalim.sinks import InMemoryRowSink
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr

from tests.testing_utils import CI_TIMEOUT_S


class _BatchStartHook(BaseHook):
    def on_batch_start(self, event) -> None:  # type: ignore[override]
        _ = event


class _LoaderCallHook(BaseHook):
    def on_loader_call(self, event) -> None:  # type: ignore[override]
        _ = event


def test_hook_capture_manager_emit_typed_gates_and_records() -> None:
    empty = HookManager()
    capture = HookCaptureManager(empty)
    capture.emit_typed(EVENT_BATCH_START, BatchStartEvent(batch_num=1, row_ids=[1]))
    assert capture.drain_events() == []

    source = HookManager()
    source.register(_BatchStartHook())
    capture = HookCaptureManager(source)
    capture.emit_typed("not-a-real-event-type", object())
    assert capture.drain_events() == []

    capture.emit_typed(EVENT_BATCH_START, BatchStartEvent(batch_num=1, row_ids=[1]))
    events = capture.drain_events()
    assert len(events) == 1
    assert events[0].event_type == EVENT_BATCH_START


@pytest.mark.parametrize(
    "policy,sample_size,result,expected",
    [
        ("full", 2, list(range(10)), list(range(10))),
        ("none", 2, list(range(10)), None),
        ("summary", 2, list(range(10)), {"type": "list", "size": 10}),
        ("sample", 2, list(range(10)), [0, 1]),
    ],
    ids=["full", "none", "summary", "sample"],
)
def test_hook_capture_manager_trigger_loader_call_policies(policy: str, sample_size: int, result: Any, expected: Any) -> None:
    source = HookManager(loader_result_policy=policy, loader_result_sample_size=sample_size)
    source.register(_LoaderCallHook())
    capture = HookCaptureManager(source)

    capture.trigger_loader_call(
        loader_name="customers",
        params={"x": 1},
        result=result,
        duration=0.01,
        batch_num=1,
    )

    events = capture.drain_events()
    assert len(events) == 1
    recorded = events[0]
    assert recorded.event_type == EVENT_LOADER_CALL
    assert recorded.payload.loader_name == "customers"
    assert recorded.payload.result == expected


def test_hook_capture_manager_trigger_loader_call_gates_no_hooks_and_no_subscription() -> None:
    empty = HookManager()
    capture = HookCaptureManager(empty)
    capture.trigger_loader_call(loader_name="x", params={}, result=[], duration=0.0, batch_num=1)
    assert capture.drain_events() == []

    source = HookManager()
    source.register(_BatchStartHook())
    capture = HookCaptureManager(source)
    capture.trigger_loader_call(loader_name="x", params={}, result=[], duration=0.0, batch_num=1)
    assert capture.drain_events() == []


def test_adaptive_loadref_parallelism_replays_in_plan_order_on_main_thread() -> None:
    started: Dict[str, threading.Event] = {"customers": threading.Event(), "products": threading.Event()}
    fast_done = threading.Event()
    fast_name = ""
    slow_name = ""
    completion_order: List[str] = []
    completion_lock = threading.Lock()

    def _barrier(name: str) -> None:
        started[name].set()
        other = "products" if name == "customers" else "customers"
        if not started[other].wait(timeout=CI_TIMEOUT_S):
            raise RuntimeError("expected concurrent start for {}".format(other))

    def _order_completion(name: str) -> None:
        _barrier(name)
        if name == slow_name and not fast_done.wait(timeout=CI_TIMEOUT_S):
            raise RuntimeError("expected {} to complete first".format(fast_name))
        with completion_lock:
            completion_order.append(name)
        if name == fast_name:
            fast_done.set()

    def _load_orders() -> List[Dict[str, Any]]:
        return [
            {"order_id": 0, "customer_id": 100, "product_id": 200},
            {"order_id": 1, "customer_id": 101, "product_id": 201},
        ]

    def _load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        _order_completion("customers")
        _ = customer_id_set
        return {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
        }

    def _load_products(product_id_set=None):  # type: ignore[no-untyped-def]
        _order_completion("products")
        _ = product_id_set
        return {
            200: {"product_id": 200, "product_name": "A"},
            201: {"product_id": 201, "product_name": "B"},
        }

    def _build_keys_params(field_name: str, param_name: str):  # type: ignore[no-untyped-def]
        def _builder(ctx):  # type: ignore[no-untyped-def]
            return (), {param_name: set(ctx.lookup_keys or set())}

        return BindingIr(key_field=field_name, params_builder=_builder, mode="keys")

    orders = MainSourceIr(source_id="orders", loader=_load_orders)

    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=_load_customers,
            bindings={"customer_id": _build_keys_params("customer_id", "customer_id_set")},
        ),
    )

    products = SourceIr(
        source_id="products",
        key=KeyIr(key="product_id"),
        loader_spec=LoaderIr(
            callable=_load_products,
            bindings={"product_id": _build_keys_params("product_id", "product_id_set")},
        ),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders, is_primary=True),
        FieldIr(
            field_id="customer_name",
            name="客户",
            source=customers,
            data_key="customer_name",
            relation=orders["customer_id"].join(customers["customer_id"]),
        ),
        FieldIr(
            field_id="product_name",
            name="商品",
            source=products,
            data_key="product_name",
            relation=orders["product_id"].join(products["product_id"]),
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers, products], fields=fields, main_source=orders)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name", "product_name"])

    expected = []
    for op in plan.operators:
        if not isinstance(op, LoadRefOperatorIr):
            continue
        expected.append(op.lookup_steps[0].to_source.source_id)
    assert len(expected) == 2
    slow_name = expected[0]
    fast_name = expected[1]

    main_thread = threading.get_ident()
    seen_thread_ids: Set[int] = set()
    seen_loader_names: List[str] = []

    class _RecordingHook(BaseHook):
        def on_loader_call(self, event) -> None:  # type: ignore[override]
            seen_loader_names.append(event.loader_name)
            seen_thread_ids.add(threading.get_ident())

    hooks = HookManager()
    hooks.register(_RecordingHook())

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=10, parallel_mode="adaptive", max_workers=2, hook_manager=hooks)
    results = engine.run(main_rows=list(_load_orders()))

    assert {r["order_id"] for r in results} == {0, 1}
    assert seen_thread_ids == {main_thread}
    assert seen_loader_names == expected
    assert completion_order == [expected[1], expected[0]]


def test_adaptive_loadref_parallelism_replays_on_event_in_plan_order_on_main_thread_streaming_sink() -> None:
    started: Dict[str, threading.Event] = {"customers": threading.Event(), "products": threading.Event()}
    fast_done = threading.Event()
    fast_name = ""
    slow_name = ""
    completion_order: List[str] = []
    completion_lock = threading.Lock()

    def _barrier(name: str) -> None:
        started[name].set()
        other = "products" if name == "customers" else "customers"
        if not started[other].wait(timeout=CI_TIMEOUT_S):
            raise RuntimeError("expected concurrent start for {}".format(other))

    def _order_completion(name: str) -> None:
        _barrier(name)
        if name == slow_name and not fast_done.wait(timeout=CI_TIMEOUT_S):
            raise RuntimeError("expected {} to complete first".format(fast_name))
        with completion_lock:
            completion_order.append(name)
        if name == fast_name:
            fast_done.set()

    def _load_orders() -> List[Dict[str, Any]]:
        return [
            {"order_id": 0, "customer_id": 100, "product_id": 200},
            {"order_id": 1, "customer_id": 101, "product_id": 201},
        ]

    def _load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        _order_completion("customers")
        _ = customer_id_set
        return {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
        }

    def _load_products(product_id_set=None):  # type: ignore[no-untyped-def]
        _order_completion("products")
        _ = product_id_set
        return {
            200: {"product_id": 200, "product_name": "A"},
            201: {"product_id": 201, "product_name": "B"},
        }

    def _build_keys_params(field_name: str, param_name: str):  # type: ignore[no-untyped-def]
        def _builder(ctx):  # type: ignore[no-untyped-def]
            return (), {param_name: set(ctx.lookup_keys or set())}

        return BindingIr(key_field=field_name, params_builder=_builder, mode="keys")

    orders = MainSourceIr(source_id="orders", loader=_load_orders)

    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=_load_customers,
            bindings={"customer_id": _build_keys_params("customer_id", "customer_id_set")},
        ),
    )

    products = SourceIr(
        source_id="products",
        key=KeyIr(key="product_id"),
        loader_spec=LoaderIr(
            callable=_load_products,
            bindings={"product_id": _build_keys_params("product_id", "product_id_set")},
        ),
    )

    fields = [
        FieldIr(field_id="order_id", name="订单ID", source=orders, is_primary=True),
        FieldIr(
            field_id="customer_name",
            name="客户",
            source=customers,
            data_key="customer_name",
            relation=orders["customer_id"].join(customers["customer_id"]),
        ),
        FieldIr(
            field_id="product_name",
            name="商品",
            source=products,
            data_key="product_name",
            relation=orders["product_id"].join(products["product_id"]),
        ),
    ]

    demand = DemandIr.from_irs(sources=[customers, products], fields=fields, main_source=orders)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name", "product_name"])

    expected = []
    for op in plan.operators:
        if not isinstance(op, LoadRefOperatorIr):
            continue
        expected.append(op.lookup_steps[0].to_source.source_id)
    assert len(expected) == 2
    slow_name = expected[0]
    fast_name = expected[1]

    main_thread = threading.get_ident()
    seen_thread_ids: Set[int] = set()
    seen_loader_names: List[str] = []

    class _OnEventHook(BaseHook):
        event_types = {EVENT_LOADER_CALL}

        def on_event(self, event) -> None:  # type: ignore[override]
            payload = event.payload
            if payload.loader_name not in started:
                return
            seen_loader_names.append(payload.loader_name)
            seen_thread_ids.add(threading.get_ident())

    hooks = HookManager()
    hooks.register(_OnEventHook())

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=10, parallel_mode="adaptive", max_workers=2, hook_manager=hooks)
    sink = InMemoryRowSink()
    result = engine.run(main_rows=list(_load_orders()), sink=sink)

    assert result == []
    assert sink.get_data()
    assert seen_thread_ids == {main_thread}
    assert seen_loader_names == expected
    assert completion_order == [expected[1], expected[0]]
