from typing import Optional

import pytest

from scalim.spec.ir import KeyIr, LookupCastSpecIr, MainSourceIr, SourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr
from scalim.utils.relation_diagnostics import RelationDiagnostics, TypeMismatchWarning


def _make_source(source_id: str, key: str = "id", key_cast: object = None) -> SourceIr:
    return SourceIr(
        source_id=source_id,
        key=KeyIr(key=key, cast=key_cast),
        loader_spec=None,  # type: ignore[arg-type]
        fk_fields=frozenset(),
        cache_mode="none",
    )


class TestTypeMismatchWarning:
    def test_creation(self) -> None:
        warning = TypeMismatchWarning(
            source_a="orders",
            field_a="customer_id",
            source_b="customers",
            field_b="id",
            message="Type mismatch: int vs str",
        )
        assert warning.source_a == "orders"
        assert warning.field_a == "customer_id"
        assert warning.source_b == "customers"
        assert warning.field_b == "id"
        assert "Type mismatch" in warning.message

    def test_extract_field_value_from_object_missing_attr(self) -> None:
        class _Row:
            pass

        assert RelationDiagnostics._extract_field_value(_Row(), "missing") is None  # noqa: SLF001
        assert RelationDiagnostics._extract_field_value({"id": 1}, "id") == 1  # noqa: SLF001

    def test_repr(self) -> None:
        warning = TypeMismatchWarning(
            source_a="a",
            field_a="f1",
            source_b="b",
            field_b="f2",
            message="test",
        )
        repr_str = repr(warning)
        assert "TypeMismatchWarning" in repr_str
        assert "a.f1" in repr_str
        assert "b.f2" in repr_str


class TestRelationDiagnosticsCheckTypeCompatibility:
    def test_no_warnings_when_types_match(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        sample_a = {1: {"order_id": 1}, 2: {"order_id": 2}}
        sample_b = {1: {"customer_id": 1}, 2: {"customer_id": 2}}

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b, sample_a, sample_b)
        assert len(warnings) == 0

    def test_warning_when_types_mismatch(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        sample_a = {1: {"order_id": 1}}
        sample_b = {"1": {"customer_id": "1"}}

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b, sample_a, sample_b)
        assert len(warnings) >= 1
        assert any("mismatch" in w.message.lower() or "lookup_cast" in w.message.lower() for w in warnings)

    def test_no_warning_when_values_match_but_keys_differ(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        sample_a = {"1": {"order_id": 1}}
        sample_b = {1: {"customer_id": 1}}

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b, sample_a, sample_b)
        assert len(warnings) == 0

    def test_type_compatibility_skips_missing_samples(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        sample_a = {1: {"order_id": None}, 2: {"order_id": 1}}
        sample_b = {1: {"customer_id": None}, 2: {"customer_id": 1}}

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b, sample_a, sample_b)
        assert len(warnings) == 0

    def test_type_compatibility_returns_without_valid_samples(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        sample_a = {1: {"order_id": None}}
        sample_b = {1: {"customer_id": 1}}

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b, sample_a, sample_b)
        assert len(warnings) == 0

    def test_no_warnings_without_sample_data(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        warnings = RelationDiagnostics.check_type_compatibility(source_a, source_b)
        assert len(warnings) == 0


class TestRelationDiagnosticsVisualizePath:
    def test_visualize_single_condition(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "Relation Path" in output
        assert "orders" in output
        assert "customers" in output

    def test_visualize_multi_condition(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")
        source_c = _make_source("countries", "country_id")

        relation = source_a["customer_id"].join(source_b["customer_id"]).and_(source_b["country_id"].join(source_c["country_id"]))

        output = RelationDiagnostics.visualize_path(relation)
        assert "Step 1" in output
        assert "Step 2" in output

    def test_visualize_with_key_field(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        relation = source_a["order_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "[KEY]" in output

    def test_visualize_with_fk_field(self) -> None:
        source_a = SourceIr(
            source_id="orders",
            key=KeyIr(key="order_id"),
            loader_spec=None,  # type: ignore[arg-type]
            fk_fields=frozenset(["customer_id"]),
            cache_mode="none",
        )
        source_b = _make_source("customers", "customer_id")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "[LOOKUP_KEY]" in output

    def test_visualize_with_transform(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast=int)

        relation = source_a["customer_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "cast" in output

    def test_visualize_with_custom_transform(self) -> None:
        class CustomTransform:
            pass

        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast=CustomTransform())

        relation = source_a["customer_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "custom" in output

    def test_visualize_with_right_fk_and_left_transform(self) -> None:
        source_a = _make_source("orders", "order_id", key_cast=str)
        source_b = SourceIr(
            source_id="customers",
            key=KeyIr(key="id"),
            loader_spec=None,  # type: ignore[arg-type]
            fk_fields=frozenset(["customer_id"]),
            cache_mode="none",
        )

        relation = source_a["order_id"].join(source_b["customer_id"])

        output = RelationDiagnostics.visualize_path(relation)
        assert "[LOOKUP_KEY]" in output
        assert "cast" in output

    def test_visualize_with_main_source_ir_has_no_key_or_cast_marks(self) -> None:
        source_a = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
        source_b = MainSourceIr(source_id="customers", loader_ref=RuntimeHandleIdIr(handle_id="customers.loader"))

        relation = source_a["customer_id"].join(source_b["customer_id"])
        output = RelationDiagnostics.visualize_path(relation)
        assert "Relation Path" in output
        assert "[KEY]" not in output
        assert "[LOOKUP_KEY]" not in output


class TestRelationDiagnosticsSampleComparison:
    def test_sample_comparison_basic(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {
            1: {"order_id": 1, "customer_id": 100},
            2: {"order_id": 2, "customer_id": 200},
        }
        data_b = {
            100: {"customer_id": 100, "name": "Alice"},
            300: {"customer_id": 300, "name": "Charlie"},
        }

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b, sample_size=10)

        assert len(results) == 2
        matched_count = sum(1 for r in results if r["matched"])
        assert matched_count == 1

    def test_sample_comparison_respects_size_limit(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {i: {"order_id": i, "customer_id": i * 10} for i in range(100)}
        data_b = {i * 10: {"customer_id": i * 10} for i in range(100)}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b, sample_size=5)
        assert len(results) == 5

    def test_sample_comparison_with_relation_ir(self) -> None:
        from scalim.spec.ir import RelationIr

        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        join_cond = source_a["customer_id"].join(source_b["customer_id"])
        relation = RelationIr(conditions=(join_cond,))

        data_a = {1: {"order_id": 1, "customer_id": 100}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["matched"] is True

    def test_sample_comparison_ignores_unrelated_conditions(self) -> None:
        from scalim.spec.ir import RelationIr

        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")
        source_c = _make_source("countries", "country_id")

        join_cond = source_a["customer_id"].join(source_b["customer_id"])
        unrelated = source_a["ignored"].join(source_c["ignored"])
        relation = RelationIr(conditions=(join_cond, unrelated))

        data_a = {1: {"order_id": 1, "customer_id": 100}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["matched"] is True

    def test_sample_comparison_empty_relation(self) -> None:
        from scalim.spec.ir import RelationIr

        relation = RelationIr(conditions=())

        data_a = {1: {"order_id": 1}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 0

    def test_sample_comparison_with_object_data(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        class OrderRow:
            def __init__(self, order_id: int, customer_id: int) -> None:
                self.order_id = order_id
                self.customer_id = customer_id

        data_a = {1: OrderRow(1, 100), 2: OrderRow(2, 200)}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 2
        assert results[0]["matched"] is True

    def test_sample_comparison_with_transform(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast=str)

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {1: {"order_id": 1, "customer_id": 100}}
        data_b = {"100": {"customer_id": "100"}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["lookup_key_normalized"] == "100"
        assert results[0]["matched"] is True

    def test_sample_comparison_with_lookup_cast_spec_registry(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast=LookupCastSpecIr(name="int"))

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {1: {"order_id": 1, "customer_id": "100"}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["lookup_key_normalized"] == 100
        assert results[0]["matched"] is True

    def test_sample_comparison_tolerates_unknown_key_cast_object(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast="nope")

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {1: {"order_id": 1, "customer_id": 100}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["lookup_key_normalized"] == 100

    def test_sample_comparison_with_transform_error(self) -> None:
        def bad_transform(v: object) -> int:
            raise ValueError("bad")

        source_a = _make_source("orders", "order_id")
        source_b = _make_source("customers", "customer_id", key_cast=bad_transform)

        relation = source_a["customer_id"].join(source_b["customer_id"])

        data_a = {1: {"order_id": 1, "customer_id": "abc"}}
        data_b = {100: {"customer_id": 100}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b)
        assert len(results) == 1
        assert results[0]["lookup_key_normalized"] is None
        assert results[0]["matched"] is False

    def test_sample_comparison_with_composite_key(self) -> None:
        source_a = _make_source("orders", "order_id")
        source_b = SourceIr(
            source_id="mapping",
            key=KeyIr(key=("region_id", "institution_id"), cast=int),
            loader_spec=None,  # type: ignore[arg-type]
            fk_fields=frozenset(),
            cache_mode="none",
        )

        relation = source_a["region_id"].join(source_b["region_id"]).and_(source_b["institution_id"].join(source_a["institution_id"]))

        data_a = {
            1: {"order_id": 1, "region_id": 1, "institution_id": 10},
            2: {"order_id": 2, "region_id": 1, "institution_id": None},
        }
        data_b = {
            (1, 10): {"region_id": 1, "institution_id": 10},
            (1, 20): {"region_id": 1, "institution_id": 20},
        }

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b, sample_size=10)
        assert len(results) == 2
        assert results[0]["lookup_key"] == (1, 10)
        assert results[0]["lookup_key_normalized"] == (1, 10)
        assert results[0]["matched"] is True
        assert results[1]["missing"] is True

    def test_sample_comparison_composite_cast_returns_none(self) -> None:
        def _cast(value: object) -> Optional[int]:
            if value == 10:
                return None
            return int(value)  # type: ignore[arg-type]

        source_a = _make_source("orders", "order_id")
        source_b = SourceIr(
            source_id="mapping",
            key=KeyIr(key=("region_id", "institution_id"), cast=_cast),
            loader_spec=None,  # type: ignore[arg-type]
            fk_fields=frozenset(),
            cache_mode="none",
        )

        relation = source_a["region_id"].join(source_b["region_id"]).and_(source_b["institution_id"].join(source_a["institution_id"]))

        data_a = {1: {"order_id": 1, "region_id": 1, "institution_id": 10}}
        data_b = {(1, 10): {"region_id": 1, "institution_id": 10}}

        results = RelationDiagnostics.sample_comparison(relation, data_a, data_b, sample_size=10)
        assert len(results) == 1
        assert results[0]["lookup_key_normalized"] is None
        assert results[0]["matched"] is False


class TestRelationDiagnosticsFormatComparisonTable:
    def test_format_empty_comparisons(self) -> None:
        output = RelationDiagnostics.format_comparison_table([])
        assert "No comparison data" in output

    def test_format_with_data(self) -> None:
        comparisons = [
            {
                "key": 1,
                "lookup_key": 100,
                "lookup_key_type": "int",
                "lookup_key_normalized": 100,
                "matched": True,
                "target_source": "customers",
            },
            {
                "key": 2,
                "lookup_key": 200,
                "lookup_key_type": "int",
                "lookup_key_normalized": 200,
                "matched": False,
                "target_source": "customers",
            },
        ]

        output = RelationDiagnostics.format_comparison_table(comparisons)
        assert "Sample Comparison" in output
        assert "Key" in output
        assert "Lookup Key" in output
        assert "Matched" in output
        assert "Yes" in output
        assert "No" in output


class TestRelationDiagnosticsHelpers:
    def test_format_key_fields_variants(self) -> None:
        fields, label = RelationDiagnostics._format_key_fields(())  # type: ignore[arg-type]
        assert fields == ()
        assert label == "()"

        fields, label = RelationDiagnostics._format_key_fields("id")
        assert fields == ("id",)
        assert label == "id"

        fields, label = RelationDiagnostics._format_key_fields(("region_id", "institution_id"))
        assert fields == ("region_id", "institution_id")
        assert label == "region_id,institution_id"

    def test_as_tuple(self) -> None:
        assert RelationDiagnostics._as_tuple(1) == (1,)
        assert RelationDiagnostics._as_tuple((1, 2)) == (1, 2)

    def test_format_field_ref_includes_sep_first_cast_details(self) -> None:
        source = _make_source("mapping", "id", key_cast=LookupCastSpecIr(name="sep_first", sep="|"))
        _key_info, transform_info = RelationDiagnostics._format_field_ref(source["id"])  # type: ignore[arg-type]
        assert "sep_first" in transform_info
        assert "sep='|'" in transform_info
