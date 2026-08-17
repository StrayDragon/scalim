from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional

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


LOOKUP_CHUNK_DEMO_ORDER_COUNT = 10


def load_orders_lookup_chunk_demo() -> List[Dict[str, object]]:
    """keys 分片演示用主源: 10 行、10 个互异 `customer_id`(与行号相同).

    互异键让 `LookupChunking.sized(N)` 的调用次数可按 `ceil(10 / N)` 直接核对,
    避免「键重复导致实际 unique keys < 行数」把分片 oracle 打糊.
    """

    return [
        {"order_id": order_id, "customer_id": order_id, "amount": (order_id + 1) * 10}
        for order_id in range(LOOKUP_CHUNK_DEMO_ORDER_COUNT)
    ]


def load_customers_by_ids(
    ids: Optional[Iterable[object]] = None,
    max_batch: Optional[int] = None,
) -> Dict[int, Dict[str, object]]:
    """keys 模式维表: 按 `$keys` 注入的 `ids` 返回客户行.

    `max_batch` 模拟下游硬限制(SQL `IN (...)` / HTTP payload / 供应商批次上限).
    超过则 fail-fast,用来演示「何时该设 `LookupChunking.sized`」.
    """

    id_list = [] if ids is None else [int(item) for item in ids]
    if max_batch is not None and len(id_list) > int(max_batch):
        msg = "customer lookup batch too large: {} ids (max_batch={})".format(len(id_list), max_batch)
        raise ValueError(msg)
    return {
        customer_id: {
            "customer_id": customer_id,
            "customer_name": "Customer-{}".format(customer_id),
        }
        for customer_id in id_list
    }


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
