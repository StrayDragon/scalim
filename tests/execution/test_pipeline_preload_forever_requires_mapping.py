import pytest

from scalim.execution import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import KeyIr, MainSourceIr, RuntimeHandleIdIr, SourceIr
from scalim.typedefs import SourceSpecIrCacheMode


def test_pipeline_preload_forever_requires_mapping_result() -> None:
    def _bad_loader():  # type: ignore[no-untyped-def]
        return [{"id": 1}]

    runtime_bindings = RuntimeBindings(source_loaders={"s1": _bad_loader})
    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr("main_source:main"))
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:s1")),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    demand = DemandIr.from_irs(sources=[source], fields=[], main_source=main)
    plan = ExecutionPlan(preload_sources=(source,))

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1)
    with pytest.raises(TypeError, match="result must be a Mapping"):
        _ = engine.run(main_rows=[])


def test_pipeline_preload_cached_sources_skips_non_preload_forever_source() -> None:
    # Regression: `_preload_cached_sources` should skip sources that are not in preload_forever mode.
    runtime_bindings = RuntimeBindings(main_source_loaders={"main": (lambda: [])})
    main = MainSourceIr(source_id="main", loader_ref=RuntimeHandleIdIr("main_source:main"))
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable_ref=RuntimeHandleIdIr("source_loader:s1")),
    )
    demand = DemandIr.from_irs(sources=[source], fields=[], main_source=main)
    plan = ExecutionPlan(preload_sources=(source,))

    engine = ScalimEngine(demand=demand, plan=plan, runtime_bindings=runtime_bindings, batch_size=1)
    assert engine.run(main_rows=[]) == []
