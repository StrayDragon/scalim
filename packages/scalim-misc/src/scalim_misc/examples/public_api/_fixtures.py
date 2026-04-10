from __future__ import annotations

from typing import Dict, List, Mapping

from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.spec.ir import CallBySpecIr, CallByValueIr, DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, RuntimeHandleIdIr

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


def load_items_key_normalization_demo() -> List[Dict[str, object]]:
    """用于演示 `key_normalization` 的最小主源数据.

    注意:
    - `dim_id` 故意使用 `str`(例如 `"1"`)
    - 对应的维表 loader 则返回 `int` key(例如 `1`),用于制造类型不一致场景
    """
    return [
        {"item_id": 1, "dim_id": "1"},
        {"item_id": 2, "dim_id": "2"},
    ]


def load_dims_key_normalization_demo_int_keys() -> Mapping[int, Dict[str, object]]:
    """用于演示 `key_normalization` 的最小维表映射.

    返回值故意使用 `int` key,用于与 `load_items_key_normalization_demo()` 的 `str` 外键制造不一致.
    """
    return {
        1: {"dim_id": 1, "dim_name": "One"},
        2: {"dim_id": 2, "dim_name": "Two"},
    }


def build_minimal_public_api_ir() -> DemandIr:
    main = MainSourceIr(source_id="items", loader_ref=RuntimeHandleIdIr(handle_id="items.main_loader"))
    fields = [
        FieldIr(field_id="item_id", name="item_id", source=main, extract_expr="item_id"),
        FieldIr(field_id="dim_id", name="dim_id", source=main, extract_expr="dim_id"),
        DerivedFieldIr(
            field_id="value_plus_one",
            name="value_plus_one",
            dependencies=("item_id",),
            call_by=CallBySpecIr(
                reference=RuntimeHandleIdIr(handle_id="derived.value_plus_one"),
                args=(CallByValueIr(kind="field", value="item_id"),),
                field_names=("item_id",),
            ),
        ),
    ]
    return DemandIr.from_irs(
        sources=[],
        fields=fields,
        main_source=main,
        batch_size_hint=10,
        name="public_api_minimal",
    )


def build_minimal_public_api_runtime_bindings() -> RuntimeBindings:
    """Build runtime bindings for `build_minimal_public_api_ir()` (Python DSL / programmatic IR path)."""

    bindings = RuntimeBindings()
    bindings.main_source_loaders["items"] = load_items

    def _value_plus_one(item_id: object) -> int:
        return int(item_id or 0) + 1

    bindings.derived_calculators["value_plus_one"] = _value_plus_one
    return bindings
