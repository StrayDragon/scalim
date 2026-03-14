from __future__ import annotations

from typing import Dict, List, Mapping

from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import MainSourceIr

_PRELOAD_COUNTER = {"calls": 0}


def reset_preload_counter_calls() -> None:
    _PRELOAD_COUNTER["calls"] = 0


def get_preload_counter_calls() -> int:
    return int(_PRELOAD_COUNTER["calls"])


def load_items() -> List[Dict[str, object]]:
    return [
        {"item_id": 1, "dim_id": "a", "value": 10},
        {"item_id": 2, "dim_id": "b", "value": 20},
        {"item_id": 3, "dim_id": "a", "value": 30},
    ]


def load_dims() -> Mapping[str, Dict[str, object]]:
    _PRELOAD_COUNTER["calls"] = int(_PRELOAD_COUNTER["calls"]) + 1
    return {
        "a": {"dim_id": "a", "dim_name": "Alpha"},
        "b": {"dim_id": "b", "dim_name": "Beta"},
    }


def build_minimal_public_api_ir() -> DemandIr:
    main = MainSourceIr(source_id="items", loader=load_items)
    fields = [
        FieldIr(field_id="item_id", name="item_id", source=main, extract_expr="item_id"),
        FieldIr(field_id="dim_id", name="dim_id", source=main, extract_expr="dim_id"),
        DerivedFieldIr(
            field_id="value_plus_one",
            name="value_plus_one",
            dependencies=("item_id",),
            calculator=lambda item_id: int(item_id or 0) + 1,
        ),
    ]
    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=main,
        batch_size_hint=10,
        name="public_api_minimal",
    )
