from dataclasses import dataclass
from typing import Any, Dict, Hashable, Iterable, List, Optional, Sequence, Tuple

from scalim.spec.ir.binding import BindingIr, LoaderCallContextIr, LoaderIr
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import DerivedFieldIr, FieldIr
from scalim.spec.ir.sources import KeyIr, MainSourceIr, SourceIr
from scalim.typedefs import RowData, SourceSpecIrCacheMode


_CUSTOMERS: Dict[int, Dict[str, Any]] = {
    1: {"customer_id": 1, "customer_name": "customer_1"},
    2: {"customer_id": 2, "customer_name": "customer_2"},
}

_COUNTRIES: Dict[int, Dict[str, Any]] = {
    86: {"country_id": 86, "country_name": "country_cn"},
    1: {"country_id": 1, "country_name": "country_us"},
}

_PAYS: Dict[int, Dict[str, Any]] = {
    100: {"pay_id": 100, "country_id": 86},
    101: {"pay_id": 101, "country_id": 1},
}

_MAPPING: Dict[Tuple[int, int], Dict[str, Any]] = {
    (1, 10): {"region_id": 1, "institution_id": 10, "mapping_name": "mapping_1_10"},
    (2, 20): {"region_id": 2, "institution_id": 20, "mapping_name": "mapping_2_20"},
}

_ORDER_TYPES: Dict[int, Dict[str, Any]] = {
    1: {"type_id": 1, "type_name": "normal"},
    2: {"type_id": 2, "type_name": "vip"},
}

_ORDERS: List[RowData] = [
    {
        "order_id": 1,
        "customer_id": 1,
        "pay_id": 100,
        "region_id": 1,
        "institution_id": 10,
        "order_type_id": 1,
        "amount": 100.0,
        "cost": 40.0,
        "source_code": 1,
    },
    {
        "order_id": 2,
        "customer_id": 2,
        "pay_id": 101,
        "region_id": 2,
        "institution_id": 20,
        "order_type_id": 2,
        "amount": 50.0,
        "cost": 20.0,
        "source_code": 2,
    },
]


def _default_binding_params(ctx: LoaderCallContextIr) -> Tuple[Tuple[Any, ...], Dict[str, Any]]:
    ids = ctx.lookup_keys_list or []
    return (), {"ids": ids, "field_keys": list(ctx.field_keys), "is_ref_loader": ctx.is_ref_loader}


def load_orders(order_ids: Optional[Sequence[int]] = None) -> Iterable[RowData]:
    if not order_ids:
        return list(_ORDERS)
    wanted = set(int(v) for v in order_ids)
    return [row for row in _ORDERS if int(row.get("order_id") or 0) in wanted]


def load_customers(ids: Optional[Sequence[Hashable]] = None, **_kwargs: Any) -> Dict[Hashable, Any]:
    if not ids:
        return dict(_CUSTOMERS)
    result: Dict[Hashable, Any] = {}
    for raw in ids:
        key = int(raw) if raw is not None else raw
        row = _CUSTOMERS.get(key)
        if row is not None:
            result[key] = dict(row)
    return result


def load_pays(ids: Optional[Sequence[Hashable]] = None, **_kwargs: Any) -> Dict[Hashable, Any]:
    if not ids:
        return dict(_PAYS)
    result: Dict[Hashable, Any] = {}
    for raw in ids:
        key = int(raw) if raw is not None else raw
        row = _PAYS.get(key)
        if row is not None:
            result[key] = dict(row)
    return result


def load_countries(ids: Optional[Sequence[Hashable]] = None, **_kwargs: Any) -> Dict[Hashable, Any]:
    if not ids:
        return dict(_COUNTRIES)
    result: Dict[Hashable, Any] = {}
    for raw in ids:
        key = int(raw) if raw is not None else raw
        row = _COUNTRIES.get(key)
        if row is not None:
            result[key] = dict(row)
    return result


def load_mapping(ids: Optional[Sequence[Hashable]] = None, **_kwargs: Any) -> Dict[Hashable, Any]:
    if not ids:
        return dict(_MAPPING)
    result: Dict[Hashable, Any] = {}
    for raw in ids:
        key = raw
        if isinstance(raw, list):
            key = tuple(raw)
        row = _MAPPING.get(key)  # type: ignore[arg-type]
        if row is not None:
            result[key] = dict(row)
    return result


def load_order_types(ids: Optional[Sequence[Hashable]] = None, **_kwargs: Any) -> Dict[Hashable, Any]:
    if not ids:
        return dict(_ORDER_TYPES)
    result: Dict[Hashable, Any] = {}
    for raw in ids:
        key = int(raw) if raw is not None else raw
        row = _ORDER_TYPES.get(key)
        if row is not None:
            result[key] = dict(row)
    return result


def _calc_profit(amount: Any, cost: Any) -> str:
    try:
        a = float(amount or 0)
        c = float(cost or 0)
    except (TypeError, ValueError):
        return "0.00"
    return "{:.2f}".format(a - c)


def _map_order_source(code: Any) -> Optional[str]:
    mapping = {1: "app", 2: "offline"}
    try:
        return mapping.get(int(code))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class MinimalIrCase:
    demand: DemandIr

    def main_rows(self, limit: Optional[int] = None) -> List[RowData]:
        rows = list(load_orders())
        if limit is None:
            return rows
        return rows[: int(limit)]


def build_minimal_ir_case() -> MinimalIrCase:
    main_source = MainSourceIr(source_id="orders", loader=load_orders)

    customers = SourceIr(
        source_id="customers",
        key=KeyIr(key="customer_id"),
        loader_spec=LoaderIr(
            callable=load_customers,
            bindings={"customer_id": BindingIr(key_field="customer_id", params_builder=_default_binding_params, as_="list")},
        ),
    )
    pays = SourceIr(
        source_id="pays",
        key=KeyIr(key="pay_id"),
        loader_spec=LoaderIr(
            callable=load_pays,
            bindings={"pay_id": BindingIr(key_field="pay_id", params_builder=_default_binding_params, as_="list")},
        ),
        fk_fields=frozenset({"country_id"}),
    )
    countries = SourceIr(
        source_id="countries",
        key=KeyIr(key="country_id"),
        loader_spec=LoaderIr(
            callable=load_countries,
            bindings={"country_id": BindingIr(key_field="country_id", params_builder=_default_binding_params, as_="list")},
        ),
    )
    mapping = SourceIr(
        source_id="mapping",
        key=KeyIr(key=("region_id", "institution_id")),
        loader_spec=LoaderIr(
            callable=load_mapping,
            bindings={
                ("region_id", "institution_id"): BindingIr(
                    key_field=("region_id", "institution_id"),
                    params_builder=_default_binding_params,
                    as_="list",
                )
            },
        ),
    )
    order_types = SourceIr(
        source_id="order_types",
        key=KeyIr(key="type_id"),
        loader_spec=LoaderIr(
            callable=load_order_types,
            bindings={"type_id": BindingIr(key_field="type_id", params_builder=_default_binding_params, as_="list")},
        ),
        cache_mode=SourceSpecIrCacheMode.PRELOAD_FOREVER,
    )

    fields = [
        FieldIr(field_id="order_id", name="Order ID", source=main_source, is_primary=True),
        FieldIr(field_id="customer_id", name="Customer ID", source=main_source),
        FieldIr(field_id="pay_id", name="Pay ID", source=main_source),
        FieldIr(field_id="region_id", name="Region ID", source=main_source),
        FieldIr(field_id="institution_id", name="Institution ID", source=main_source),
        FieldIr(field_id="order_type_id", name="Order Type ID", source=main_source),
        FieldIr(field_id="amount", name="Amount", source=main_source),
        FieldIr(field_id="cost", name="Cost", source=main_source),
        FieldIr(field_id="source_code", name="Source Code", source=main_source),
        FieldIr(
            field_id="order_source",
            name="Order Source",
            source=main_source,
            data_key="source_code",
            transform=_map_order_source,
        ),
        FieldIr(
            field_id="customer_name",
            name="Customer Name",
            source=customers,
            relation=main_source["customer_id"].join(customers["customer_id"]),
        ),
        FieldIr(
            field_id="country_name",
            name="Country Name",
            source=countries,
            relation=main_source["pay_id"].join(pays["pay_id"]).and_(pays["country_id"].join(countries["country_id"])),
        ),
        FieldIr(
            field_id="mapping_name",
            name="Mapping Name",
            source=mapping,
            relation=main_source["region_id"]
            .join(mapping["region_id"])
            .and_(main_source["institution_id"].join(mapping["institution_id"])),
        ),
        FieldIr(
            field_id="order_type_name",
            name="Order Type Name",
            source=order_types,
            data_key="type_name",
            relation=main_source["order_type_id"].join(order_types["type_id"]),
        ),
        DerivedFieldIr(
            field_id="profit",
            name="Profit",
            dependencies=("amount", "cost"),
            calculator=lambda amount, cost: _calc_profit(amount=amount, cost=cost),
        ),
    ]

    demand = DemandIr.from_irs(
        sources=[customers, pays, countries, mapping, order_types],
        fields=fields,
        main_source=main_source,
        name="minimal_ir",
    )
    return MinimalIrCase(demand=demand)


__all__ = [
    "MinimalIrCase",
    "build_minimal_ir_case",
]
