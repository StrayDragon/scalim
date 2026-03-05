import threading
from typing import Any, Dict, List, Set

import pytest

from scalim.events.catalog import EVENT_LOADER_CALL
from scalim.ob.manager import ObserverCaptureOverflowError, ObserverManager
from scalim.ob.observer import Observer
from scalim.planning import PlanBuilder
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr


class _LoaderCallObserver(Observer):
    event_types = {EVENT_LOADER_CALL}

    def __init__(self) -> None:
        self.thread_ids: Set[int] = set()
        self.loader_names: List[str] = []

    def on_event(self, event) -> None:  # type: ignore[override]
        self.thread_ids.add(threading.get_ident())
        self.loader_names.append(event.payload.loader_name)


def test_observer_manager_capture_overflow_default_policy_raises() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=1)
    manager.emit_event("x", 1)
    with pytest.raises(ObserverCaptureOverflowError, match="capture recorded events overflow"):
        manager.emit_event("x", 2)

    drained = manager.drain_events()
    assert len(drained) == 1
    assert drained[0].payload == 1


def test_observer_manager_capture_overflow_drop_oldest_keeps_last_n() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=2, capture_overflow_policy="drop-oldest")
    manager.emit_event("x", 0)
    manager.emit_event("x", 1)
    manager.emit_event("x", 2)

    drained = manager.drain_events()
    assert [event.payload for event in drained] == [1, 2]


def test_observer_manager_capture_overflow_drop_newest_keeps_first_n() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=2, capture_overflow_policy="drop-newest")
    manager.emit_event("x", 0)
    manager.emit_event("x", 1)
    manager.emit_event("x", 2)

    drained = manager.drain_events()
    assert [event.payload for event in drained] == [0, 1]


def test_observer_manager_capture_limit_can_be_disabled_with_none() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=None)
    manager.emit_event("x", 0)
    manager.emit_event("x", 1)
    manager.emit_event("x", 2)
    assert [event.payload for event in manager.drain_events()] == [0, 1, 2]


def test_observer_manager_capture_limit_zero_drops_when_configured() -> None:
    manager = ObserverManager(mode="capture", max_recorded_events=0, capture_overflow_policy="drop-oldest")
    manager.emit_event("x", 1)
    assert manager.drain_events() == []


def test_observer_manager_rejects_negative_max_recorded_events() -> None:
    with pytest.raises(ValueError, match="max_recorded_events must be >= 0"):
        _ = ObserverManager(max_recorded_events=-1)


def test_observer_manager_rejects_unknown_capture_overflow_policy() -> None:
    with pytest.raises(ValueError, match="Unknown capture_overflow_policy"):
        _ = ObserverManager(capture_overflow_policy="unknown")


def test_observer_manager_setstate_backfills_recorded_events_when_missing() -> None:
    state = ObserverManager().__getstate__()
    state.pop("_recorded_events", None)

    restored = ObserverManager.__new__(ObserverManager)
    restored.__setstate__(state)

    assert restored.drain_events() == []


def test_observer_manager_setstate_converts_recorded_events_list_to_deque() -> None:
    state = ObserverManager().__getstate__()
    state["_recorded_events"] = []
    state["mode"] = "capture"

    restored = ObserverManager.__new__(ObserverManager)
    restored.__setstate__(state)

    restored.emit_event("x", 1)
    assert [event.payload for event in restored.drain_events()] == [1]


def _build_two_ref_plan() -> DemandIr:
    def _load_orders() -> List[Dict[str, Any]]:
        return [
            {"order_id": 0, "customer_id": 100, "product_id": 200},
            {"order_id": 1, "customer_id": 101, "product_id": 201},
        ]

    def _load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        _ = customer_id_set
        return {
            100: {"customer_id": 100, "customer_name": "Alice"},
            101: {"customer_id": 101, "customer_name": "Bob"},
        }

    def _load_products(product_id_set=None):  # type: ignore[no-untyped-def]
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

    return DemandIr.from_irs(sources=[customers, products], fields=fields, main_source=orders)


def test_adaptive_capture_replay_replays_observer_events_on_main_thread_in_plan_order() -> None:
    from scalim.execution import ScalimEngine

    demand = _build_two_ref_plan()
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name", "product_name"])

    expected: List[str] = []
    for op in plan.operators:
        if getattr(op, "operator_type", None) != "load_ref":
            continue
        expected.append(op.lookup_steps[0].to_source.source_id)
    assert len(expected) == 2

    observer = _LoaderCallObserver()
    manager = ObserverManager(observers=[observer])
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=10, parallel_mode="adaptive", max_workers=2, observer_manager=manager)
    rows = engine.run(
        main_rows=[
            {"order_id": 0, "customer_id": 100, "product_id": 200},
            {"order_id": 1, "customer_id": 101, "product_id": 201},
        ]
    )

    assert {r["order_id"] for r in rows} == {0, 1}
    assert observer.loader_names == expected
    assert observer.thread_ids == {threading.get_ident()}


def test_adaptive_capture_overflow_is_diagnosable() -> None:
    from scalim.execution import ScalimEngine

    demand = _build_two_ref_plan()
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name", "product_name"])

    observer = _LoaderCallObserver()
    manager = ObserverManager(observers=[observer], max_recorded_events=0, capture_overflow_policy="raise")
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=10, parallel_mode="adaptive", max_workers=2, observer_manager=manager)

    with pytest.raises(ObserverCaptureOverflowError, match="capture recorded events overflow"):
        _ = engine.run(
            main_rows=[
                {"order_id": 0, "customer_id": 100, "product_id": 200},
                {"order_id": 1, "customer_id": 101, "product_id": 201},
            ]
        )
