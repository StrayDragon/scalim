import pytest

from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.models import FieldDef


def test_select_field_defs_rejects_missing_required_field() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match="Required field 'missing' is not defined"):
        _ = loader._select_field_defs(
            ["missing"],
            defs_by_id={},
            all_field_defs=[],
        )


def test_select_field_defs_rejects_ambiguous_required_field() -> None:
    loader = YamlDemandLoader()

    d1 = FieldDef(field_id="dup", kind="source", data={"extract": "x"}, source_id="orders")
    d2 = FieldDef(field_id="dup", kind="source", data={"extract": "y"}, source_id="orders")

    with pytest.raises(ValueError, match="defined multiple times"):
        _ = loader._select_field_defs(
            ["dup"],
            defs_by_id={"dup": [d1, d2]},
            all_field_defs=[d1, d2],
        )


def test_ensure_unique_field_ids_rejects_duplicates() -> None:
    loader = YamlDemandLoader()

    d1 = FieldDef(field_id="order_id", kind="source", data={"extract": "order_id"}, source_id="orders")
    d2 = FieldDef(field_id="order_id", kind="source", data={"extract": "order_id"}, source_id="orders")

    with pytest.raises(ValueError, match="rename the field_id"):
        loader._ensure_unique_field_ids([d1, d2])


def test_collect_required_field_defs_enqueues_nested_derived_dependencies() -> None:
    loader = YamlDemandLoader()

    # a -> b -> order_id
    a = FieldDef(field_id="a", kind="derived", data={"compute": "b"})
    b = FieldDef(field_id="b", kind="derived", data={"compute": "order_id"})
    order_id = FieldDef(field_id="order_id", kind="source", data={"extract": "order_id"}, source_id="orders")

    defs_by_id = {
        "a": [a],
        "b": [b],
        "order_id": [order_id],
    }

    required = loader._collect_required_field_defs([a], defs_by_id)

    required_ids = {d.field_id for d in required}
    assert required_ids == {"a", "b", "order_id"}
