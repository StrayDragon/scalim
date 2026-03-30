import pytest

from scalim.execution import ScalimEngine
from scalim.planning.plan import ExecutionPlan
from scalim.spec.ir.binding import LoaderIr
from scalim.spec.ir import DemandIr
from scalim.spec.ir import KeyIr, MainSourceIr, SourceIr
from scalim.typedefs import SourceSpecIrCacheMode


def test_pipeline_preload_forever_requires_mapping_result() -> None:
    def _bad_loader():  # type: ignore[no-untyped-def]
        return [{"id": 1}]

    main = MainSourceIr(source_id="main", loader=lambda: [])
    source = SourceIr(
        source_id="s1",
        key=KeyIr(key="id"),
        loader_spec=LoaderIr(callable=_bad_loader),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )
    demand = DemandIr.from_irs(sources=[source], fields=[], main_source=main)
    plan = ExecutionPlan(preload_sources=(source,))

    engine = ScalimEngine(demand=demand, plan=plan, batch_size=1)
    with pytest.raises(TypeError, match="result must be a Mapping"):
        _ = engine.run(main_rows=[])
