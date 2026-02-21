from __future__ import annotations

from typing import Any, Dict, List

from scalim.execution.pipeline.base.pipeline import SeqPipeline
from scalim.execution.executor.helpers.relation_signature import build_relation_signature, can_group_by_relation
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.hooks.base import HookManager
from scalim.ob.manager import ObserverManager
from scalim.planning.operators import LoadRefOperatorIr
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import BindingIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.relations import LookupStepIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from tests.testing_utils import StreamingListSink


class _NoOpExecutor:
    def __init__(self, operators: List[Any]) -> None:
        self._operators = list(operators)

    def prefill_main_source_fields(self, context, batch_rows, required_fields) -> None:  # type: ignore[no-untyped-def]
        _ = context, batch_rows, required_fields

    def execute_operators(  # type: ignore[no-untyped-def]
        self,
        context,
        row_ids,
        *,
        runtime: ExecutionRuntime,
        required_fields,
        adaptive_pool=None,
        after_operator=None,
    ):
        _ = context, row_ids, required_fields, adaptive_pool
        for operator in self._operators:
            if isinstance(operator, LoadRefOperatorIr) and can_group_by_relation(operator.lookup_steps):
                runtime.load_ref_group_executed.add(build_relation_signature(operator.lookup_steps))
            if after_operator is not None:
                after_operator(operator)
        return None


def test_streaming_rows_binding_barriers_cover_groupable_and_non_groupable_paths() -> None:
    main_source = MainSourceIr(source_id="main", loader=lambda: [])
    demand = DemandIr.from_irs(sources=[], fields=[], main_source=main_source)

    ref_source = SourceIr(source_id="ref", key=KeyIr(key="id"), loader_spec=LoaderIr(callable=lambda: {}))

    groupable_step = LookupStepIr(
        from_field="fk",
        to_source=ref_source,
        bind=BindingIr(key_field="fk", params_builder=lambda ctx: ((), {}), mode="rows", cache_mode="batch"),
    )
    non_groupable_step = LookupStepIr(
        from_field="fk2",
        to_source=ref_source,
        bind=BindingIr(key_field="fk2", params_builder=lambda ctx: ((), {}), mode="rows", cache_mode="none"),
    )

    field_groupable = FieldIr(field_id="ref_name", name="RefName", source=ref_source, lookup_steps=(groupable_step,))
    field_non_groupable = FieldIr(field_id="ref_desc", name="RefDesc", source=ref_source, lookup_steps=(non_groupable_step,))

    op_groupable = LoadRefOperatorIr(
        operator_id="load_ref:groupable",
        operator_type="load_ref",
        source=ref_source,
        field_key="ref_name",
        field_spec=field_groupable,
        lookup_steps=(groupable_step,),
    )
    op_non_groupable = LoadRefOperatorIr(
        operator_id="load_ref:non_groupable",
        operator_type="load_ref",
        source=ref_source,
        field_key="ref_desc",
        field_spec=field_non_groupable,
        lookup_steps=(non_groupable_step,),
    )

    plan = ExecutionPlan(
        operators=(op_non_groupable, op_groupable),
        field_specs={},
        field_dependencies={},
        target_fields=[],
    )

    hook_manager = HookManager()
    observer_manager = ObserverManager()
    runtime = ExecutionRuntime(plan, hook_manager, observer_manager, main_source=main_source)
    executor = _NoOpExecutor([op_non_groupable, op_groupable])

    pipeline = SeqPipeline(
        plan=plan,
        executor=executor,  # type: ignore[arg-type]
        runtime=runtime,
        hook_manager=hook_manager,
        observer_manager=observer_manager,
        demand=demand,
        batch_size=10,
    )

    sink = StreamingListSink()
    row_ids = [0]
    batch_rows: Dict[int, dict] = {0: {"fk": 1, "fk2": 2}}
    result = pipeline._execute_batch_streaming_mode(row_ids, batch_rows, sink, batch_num=1)  # noqa: SLF001

    assert result == []
