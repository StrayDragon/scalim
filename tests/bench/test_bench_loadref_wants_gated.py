import os
from typing import Dict, List, Sequence

import pytest

from scalim._project_constants import ENV_BENCH_SCALE, ENV_BENCH_SCOPE
from scalim.events import EVENT_RELATION_LOOKUP
from scalim.execution.context import BatchContext
from scalim.execution.executor.operators.load_ref.executor import LoadRefOperatorExecutor
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import EventDispatchObserver
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import LookupStepIr
from scalim.spec.ir import KeyIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim_benchlib import BenchmarkRunner


def _bench_scale() -> str:
    return os.getenv(ENV_BENCH_SCALE, "small")


def _bench_scope() -> str:
    return os.getenv(ENV_BENCH_SCOPE, "loadref-fastpath")


def _bench_row_count() -> int:
    scale = _bench_scale()
    return {
        "small": 200,
        "medium": 1000,
        "large": 5000,
    }.get(scale, 200)


def _bench_info(scenario: str, row_count: int) -> Dict[str, object]:
    return {
        "scenario": scenario,
        "scale": _bench_scale(),
        "scope": _bench_scope(),
        "row_count": row_count,
    }


class _NoopRelationLookupObserver(EventDispatchObserver):
    event_types = {EVENT_RELATION_LOOKUP}

    def on_relation_lookup(self, _payload) -> None:  # type: ignore[no-untyped-def]
        return


def _make_operator() -> LoadRefOperatorIr:
    target_source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr(handle_id="targets.loader")),
    )
    binding = BindingIr(key_field="target_id", params_builder_ref=RuntimeHandleIdIr(handle_id="targets.target_id.params_builder"))
    steps = (LookupStepIr(from_field="fk_id", to_source=target_source, bind=binding),)
    return LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id=target_source.source_id,
        field_key="target_name",
        lookup_steps=steps,
    )


@pytest.mark.bench
@pytest.mark.parametrize(
    "wanted",
    [False, True],
    ids=["unwanted", "wanted"],
)
@pytest.mark.benchmark(group="loadref-fastpath")
def test_bench_loadref_relation_lookup_wants_gated(benchmark, wanted: bool) -> None:
    row_count = _bench_row_count()
    batch_row_nth: List[int] = list(range(row_count))

    def _loader(target_ids: Sequence[int]) -> Dict[int, Dict[str, object]]:
        return {key: {"name": "Name{}".format(key)} for key in target_ids}

    operator = _make_operator()
    target_source = operator.lookup_steps[0].to_source
    runtime_bindings = RuntimeBindings(
        main_source_loaders={"main": lambda: []},
        source_loaders={"targets": _loader},
        params_builders={
            ("targets", "target_id"): lambda ctx: ((), {"target_ids": list(ctx.lookup_keys or [])}),
        },
    )
    plan = ExecutionPlan(
        operators=(operator,),
        field_specs={"target_name": FieldIr(field_id="target_name", name="Target", source=target_source, data_key="name")},
        target_fields=["target_name"],
    )
    runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(fallback_logger_enabled=False),
        observer_manager=ObserverManager(fallback_logger_enabled=False),
        main_source=MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr(handle_id="main.loader")),
        sources={"targets": target_source},
        runtime_bindings=runtime_bindings,
    )
    if wanted:
        runtime.observer_manager.register(_NoopRelationLookupObserver())
    executor = LoadRefOperatorExecutor()

    def _run() -> int:
        runtime.reset_load_ref_cache()
        ctx = BatchContext()
        for row_id in batch_row_nth:
            ctx.set_field_value("fk_id", row_id, row_id)
        executor.execute(operator, ctx, batch_row_nth, runtime)
        return row_count

    scenario = "relation_lookup_{}".format("wanted" if wanted else "unwanted")
    runner = BenchmarkRunner(benchmark)
    runner.run(_run, extra_info=_bench_info(scenario, row_count))
