"""探针: adaptive 层退化串行(单 LoadRef)时, chunk 并行是否在 worker 线程直接回调用户 observer/hook."""

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from scalim.events import Event, EventType
from scalim.execution.adaptive.loadref_scheduler import AdaptiveLoadRefScheduler
from scalim.execution.chunk_parallelism import LookupChunkParallelismPolicy
from scalim.execution.context import BatchContext
from scalim.execution.executor.runtime.runtime import ExecutionRuntime
from scalim.execution.pipeline.overrides import PipelineOverrides
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.hooks import HookManager
from scalim.ob.manager import ObserverManager
from scalim.ob.observer import Observer
from scalim.planning.operators import LoadRefOperatorIr, OperatorType
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir import FieldIr, KeyIr, LookupStepIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.spec.ir.binding import BindingIr, LoaderIr


class _ThreadNameObserver(Observer):
    event_types = {EventType.LOADER_CALL}

    def __init__(self) -> None:
        self.threads: List[str] = []

    def on_event(self, event: Event) -> None:
        self.threads.append(threading.current_thread().name)


def main() -> None:
    observer = _ThreadNameObserver()
    runtime_bindings = RuntimeBindings()

    def _loader(ids: List[int]) -> Dict[int, Dict[str, Any]]:
        return {key: {"name": "Name{}".format(key)} for key in ids}

    runtime_bindings.source_loaders["targets"] = _loader
    runtime_bindings.params_builders[("targets", "target_id")] = lambda ctx: ((), {"ids": list(ctx.lookup_keys_list or [])})

    source = SourceIr(
        source_id="targets",
        key=KeyIr(key="target_id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:targets")),
        lookup_chunk_size=2,
    )
    binding = BindingIr(key_field="target_id", params_builder_ref=RuntimeHandleIdIr("params_builder:targets:target_id"))
    field_spec = FieldIr(field_id="target_name", name="Target", source=source, data_key="name")
    op = LoadRefOperatorIr(
        operator_id="load_ref",
        operator_type=OperatorType.LOAD_REF.value,
        source_id="targets",
        field_key="target_name",
        lookup_steps=(LookupStepIr(from_field="fk_id", to_source=source, bind=binding),),
    )
    plan = ExecutionPlan(field_specs={"target_name": field_spec}, operators=(op,))

    runtime = ExecutionRuntime(
        plan=plan,
        hook_manager=HookManager(),
        observer_manager=ObserverManager(observers=[observer]),
        main_source=MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr("main_source:orders")),
        sources={"targets": source},
        runtime_bindings=runtime_bindings,
        parallel_mode="adaptive",
        max_workers=4,
        chunk_parallelism=LookupChunkParallelismPolicy(parallelize_lookup_chunks=True),
    )

    context = BatchContext()
    row_ids = list(range(1, 9))
    for row_id in row_ids:
        context.set_field_value("fk_id", row_id, row_id)

    scheduler = AdaptiveLoadRefScheduler(plan, overrides=PipelineOverrides())
    with ThreadPoolExecutor(max_workers=4) as pool:
        scheduler.execute_segment(
            [op],  # 单个 LoadRef -> below_min_parallel_tasks -> 层退化串行(主 runtime, 真实 observer)
            context=context,
            batch_row_nth=row_ids,
            runtime=runtime,
            pool=pool,
            max_workers=4,
            required_fields=None,
            after_operator=None,
        )

    main_thread = threading.current_thread().name
    print("main thread      :", main_thread)
    print("observer threads :", observer.threads)
    print("callbacks off main thread:", [t for t in observer.threads if t != main_thread])


if __name__ == "__main__":
    main()
