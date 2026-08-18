import hashlib
from typing import Any, Dict, List

from scalim.events import EventType
from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import BaseHook, HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.presets.performance import PerformanceConfig, PerformanceObserver
from scalim.ob.presets.profiles import PROFILE_BENCH, build_observability_profile
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryColumnSink, InMemoryCsvSink
from scalim.spec.ir import BindingIr, DemandIr, FieldIr, KeyIr, LoaderIr, MainSourceIr, RuntimeHandleIdIr, SourceIr


class _StageSpanHook(BaseHook):
    event_types = {EventType.STAGE_SPAN}

    def __init__(self) -> None:
        self.by_stage = {"loader": 0.0, "compute": 0.0, "write": 0.0, "stream": 0.0}
        self.write_events = 0

    def on_event(self, event) -> None:  # type: ignore[override]
        if event.event_type != EventType.STAGE_SPAN:
            return
        payload = event.payload
        stage = str(payload.stage)
        self.by_stage[stage] = self.by_stage.get(stage, 0.0) + float(payload.duration)
        if stage == "write":
            self.write_events += 1


def _make_case():
    def load_orders() -> List[Dict[str, Any]]:
        return [{"order_id": 1, "customer_id": 10}, {"order_id": 2, "customer_id": 10}]

    def load_customers(customer_id_set=None):  # type: ignore[no-untyped-def]
        _ = customer_id_set
        return {10: {"customer_id": 10, "customer_name": "A"}}

    def _build_keys_params(field_name: str, param_name: str) -> BindingIr:
        return BindingIr(
            key_field=field_name,
            params_builder_ref=RuntimeHandleIdIr(handle_id="customers.params_builder.{}".format(field_name)),
            param_name=param_name,
            mode="keys",
        )

    orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable_ref=RuntimeHandleIdIr(handle_id="customers.loader"),
            bindings={"customer_id": _build_keys_params("customer_id", "customer_id_set")},
        ),
    )
    fields = [
        FieldIr(field_id="order_id", name="订单ID", source_id=orders.source_id, is_primary=True),
        FieldIr(
            field_id="customer_name",
            name="客户",
            source_id=customers.source_id,
            data_key="customer_name",
            relation=orders["customer_id"].join(customers["customer_id"]),
        ),
    ]
    demand = DemandIr.from_irs(sources=[customers], fields=fields, main_source=orders)
    plan = PlanBuilder(demand).build(targets=["order_id", "customer_name"])
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"orders": load_orders},
        source_loaders={"customers": load_customers},
        params_builders={
            ("customers", "customer_id"): (lambda ctx: ((), {"customer_id_set": set(ctx.lookup_keys or set())})),
        },
    )
    return demand, plan, runtime_bindings, load_orders


from scalim.execution.pipeline.overrides import PipelineOverrides


class _FakeClock(object):
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        self.t += 0.01
        return self.t


def test_column_write_stage_positive_and_not_double_counted():
    demand, plan, runtime_bindings, load_orders = _make_case()
    hook = _StageSpanHook()
    hooks = HookManager()
    hooks.register(hook)
    perf = PerformanceObserver(config=PerformanceConfig(metrics={"duration"}, report_format="none"))
    clock = _FakeClock()

    engine = ScalimEngine(
        demand=demand,
        plan=plan,
        runtime_bindings=runtime_bindings,
        batch_size=10,
        parallel_mode="seq",
        hook_manager=hooks,
        observer_manager=ObserverManager(observers=[perf]),
        pipeline_overrides=PipelineOverrides(stage_perf_counter_fn=clock),
    )
    with InMemoryColumnSink(field_names=plan.target_fields) as sink:
        _ = engine.run(main_rows=list(load_orders()), sink=sink)

    assert hook.write_events > 0
    assert hook.by_stage["write"] > 0.0
    assert perf.metrics.stage_metrics.write_duration > 0.0
    stage_sum = (
        float(perf.metrics.stage_metrics.loader_duration)
        + float(perf.metrics.stage_metrics.compute_duration)
        + float(perf.metrics.stage_metrics.write_duration)
    )
    assert stage_sum <= float(perf.metrics.total_duration) + 1.0


def test_write_attribution_does_not_change_csv_bytes():
    demand, plan, runtime_bindings, load_orders = _make_case()

    def _run(with_obs: bool) -> bytes:
        sink = InMemoryCsvSink(field_names=list(plan.target_fields))
        observers = []
        if with_obs:
            built = build_observability_profile(PROFILE_BENCH, include_memory=False)
            observers = list(built["components"])
        engine = ScalimEngine(
            demand=demand,
            plan=plan,
            runtime_bindings=runtime_bindings,
            batch_size=10,
            parallel_mode="seq",
            observer_manager=ObserverManager(observers=observers) if observers else None,
        )
        with sink:
            _ = engine.run(main_rows=list(load_orders()), sink=sink)
        artifact = sink.to_artifact()
        payload = repr(artifact.header) + "|" + repr(artifact.rows)
        return payload.encode("utf-8")

    assert hashlib.sha256(_run(False)).hexdigest() == hashlib.sha256(_run(True)).hexdigest()
