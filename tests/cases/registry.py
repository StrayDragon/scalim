from dataclasses import dataclass
from typing import Callable, Dict, Sequence

from scalim.spec.ir.demand import DemandIr

from .minimal_ir import build_minimal_ir_case


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    build_demand: Callable[[], DemandIr]
    default_targets: Sequence[str]


def _build_minimal_ir_demand() -> DemandIr:
    return build_minimal_ir_case().demand


_CASES: Dict[str, CaseSpec] = {
    "minimal_ir": CaseSpec(
        case_id="minimal_ir",
        build_demand=_build_minimal_ir_demand,
        default_targets=("order_id", "profit", "customer_name", "country_name", "mapping_name", "order_type_name"),
    ),
}


def get_case(case_id: str) -> CaseSpec:
    if case_id not in _CASES:
        msg = "Unknown case_id={!r}. Known: {}".format(case_id, ", ".join(sorted(_CASES)))
        raise KeyError(msg)
    return _CASES[case_id]


__all__ = [
    "CaseSpec",
    "get_case",
]
