from typing import Any, Dict, List, Sequence

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink
from scalim.typedefs import RowData

from ..loaders import ECommerceConfig, set_config
from ..shared import build_ecommerce_model
from ..verification import VerificationResult, verify_scalim_output
from ._types import ChapterResult


def _run(cfg: ECommerceConfig, targets: Sequence[str], *, parallel_mode: str, batch_size: int) -> List[RowData]:
    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    plan = PlanBuilder(demand).build(targets=list(targets))
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size), parallel_mode=parallel_mode)
    with InMemoryColumnSink(field_names=list(targets)) as sink:
        _ = engine.run(main_rows=None, sink=sink)
        rows: List[RowData] = sink.get_rows()
        return rows


def run_parallel_mode(cfg: ECommerceConfig, *, targets: Sequence[str], batch_size: int = 50) -> ChapterResult:
    """`seq` vs `adaptive` 的一致性对拍."""
    targets_list = list(targets)
    rows_seq = _run(cfg, targets_list, parallel_mode="seq", batch_size=batch_size)
    rows_adaptive = _run(cfg, targets_list, parallel_mode="adaptive", batch_size=batch_size)

    vr_seq: VerificationResult = verify_scalim_output(rows_seq, fields_to_check=targets_list)
    vr_adaptive: VerificationResult = verify_scalim_output(rows_adaptive, fields_to_check=targets_list)

    passed = bool(vr_seq.passed and vr_adaptive.passed and len(rows_seq) == len(rows_adaptive))
    summary = "rows={} verify_seq={} verify_adaptive={}".format(len(rows_seq), vr_seq.passed, vr_adaptive.passed)
    if not vr_seq.passed:
        summary = summary + "\nseq: " + vr_seq.summary
    if not vr_adaptive.passed:
        summary = summary + "\nadaptive: " + vr_adaptive.summary

    details: Dict[str, Any] = {
        "rows": len(rows_seq),
        "verify_seq": vr_seq,
        "verify_adaptive": vr_adaptive,
    }
    return ChapterResult(chapter_id="parallel_mode", passed=passed, summary=summary, details=details)
