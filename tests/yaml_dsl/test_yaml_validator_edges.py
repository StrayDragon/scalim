import pytest

import scalim.dsl.yaml_dsl._internal.config_parsing.validator as validator_module
from scalim.dsl.yaml_dsl._internal.config_parsing.models import AliasIndex, FieldDef, RawDemand


class _WeirdStr(str):
    def split(self, sep=None, maxsplit=-1):  # type: ignore[override]
        return ["only"]


def _field_def(field_id, kind="source", source_id=None, field="id", data=None):
    payload = data if data is not None else {"extract": field}
    return FieldDef(field_id=str(field_id), kind=kind, source_id=source_id, data=payload)


def _assert_validation_errors(config: dict, *expected_messages: str) -> None:
    validator = validator_module.ConfigValidator()

    with pytest.raises(validator_module.ScalimConfigValidationError) as exc:
        validator.validate(config)

    errors = exc.value.errors
    for message in expected_messages:
        assert any(message in msg for msg in errors)


def _messages(errors):
    output = []
    for issue in errors:
        message = getattr(issue, "message", None)
        output.append(message if message is not None else str(issue))
    return output


def test_validator_required_and_legacy_fields_edges() -> None:
    config = {
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
        "sources": {"bad": "nope"},
        "fields": {"bad_field": "oops"},
        "foreign_key": "id",
    }

    _assert_validation_errors(config, "Missing required field: 'name'", "Legacy field 'foreign_key'")


def test_validator_rejects_unknown_top_level_field() -> None:
    config = {
        "name": "demo",
        "dsl_version": "2.0",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
        "sources": {},
    }

    validator = validator_module.ConfigValidator()
    report = validator.validate_report(config, strict_unknown_fields=True)
    errors = report.errors()

    assert any("Unknown field 'dsl_version'" in msg for msg in _messages(errors))
    assert any(issue.path == "dsl_version" for issue in errors)
    assert not any("Schema validation error" in msg for msg in _messages(errors))


def test_validator_validate_sources_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    assert validator._validate_sources({"sources": []}, errors) == {}

    errors = []
    validator._validate_sources({"sources": {"bad": []}}, errors)
    assert any("Source 'bad' must be a dictionary" in msg for msg in _messages(errors))

    errors = []
    validator._validate_sources({"sources": {"s1": {"loader": "bad ref", "key": "id"}}}, errors)
    assert any("loader 引用" in msg for msg in _messages(errors))


def test_validator_validate_main_source_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    validator._validate_main_source({"main_source": []}, errors)
    assert any("main_source" in msg for msg in _messages(errors))

    errors = []
    validator._validate_main_source(
        {
            "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
            "sources": {"orders": {"loader": "tests.fixtures.mock_loaders.mock_loader", "key": "id"}},
        },
        errors,
    )
    assert any("must not appear" in msg for msg in _messages(errors))


def test_validator_collect_main_source_fields_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    sources_set = {"orders"}
    sources_info = {"orders": {"bind": False, "preload": False}}
    relation_paths = {}

    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()
    duplicate_fields_by_source = {}
    seen_field_values_by_source = {}

    validator._collect_main_source_fields(
        RawDemand.from_raw({"main_source": []}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )

    validator._collect_main_source_fields(
        RawDemand.from_raw({"main_source": {"fields": []}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("main_source.fields" in msg for msg in _messages(errors))

    validator._collect_main_source_fields(
        RawDemand.from_raw({"main_source": {"fields": {"bad": {"compute": "x"}}}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("must not declare compute" in msg for msg in _messages(errors))

    validator._collect_main_source_fields(
        RawDemand.from_raw({"main_source": {"fields": {"ok": 1}}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("Field 'ok' must be a dictionary" in msg for msg in _messages(errors))


def test_validator_require_compute_engine_guard() -> None:
    validator = validator_module.ConfigValidator()
    validator._compute_engine = None

    with pytest.raises(RuntimeError, match="not initialized"):
        validator._require_compute_engine()


def test_validator_add_field_def_requires_dict() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()

    assert validator._add_field_def("f", "source", "orders", 1, field_defs, defs_by_id, alias_index, errors) is None
    assert any("Field 'f' must be a dictionary" in msg for msg in _messages(errors))


def test_validator_collect_source_fields_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    sources_set = {"orders", "s1"}
    sources_info = {"orders": {"bind": False, "preload": False}, "s1": {"bind": False, "preload": False}}
    relation_paths = {}

    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()
    duplicate_fields_by_source = {}
    seen_field_values_by_source = {}

    validator._collect_source_fields(
        RawDemand.from_raw({"sources": []}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )

    validator._collect_source_fields(
        RawDemand.from_raw({"sources": {"s1": []}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )

    validator._collect_source_fields(
        RawDemand.from_raw({"sources": {"s1": {"fields": []}}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("sources.s1.fields" in msg for msg in _messages(errors))

    validator._collect_source_fields(
        RawDemand.from_raw({"sources": {"s1": {"fields": {"bad": {"compute": "x"}}}}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("must not declare compute" in msg for msg in _messages(errors))

    validator._collect_source_fields(
        RawDemand.from_raw({"sources": {"s1": {"fields": {"ok": 1}}}}),
        errors,
        sources_set,
        sources_info,
        "orders",
        relation_paths,
        field_defs,
        defs_by_id,
        alias_index,
        duplicate_fields_by_source,
        seen_field_values_by_source,
    )
    assert any("Field 'ok' must be a dictionary" in msg for msg in _messages(errors))


def test_validator_collect_derived_fields_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    field_defs = []
    defs_by_id = {}
    alias_index = AliasIndex()
    derived_fields_with_deps = []

    validator._collect_derived_fields(
        RawDemand.from_raw({"fields": []}),
        errors,
        field_defs,
        defs_by_id,
        alias_index,
        derived_fields_with_deps,
    )
    assert any("'fields' must be a dictionary" in msg for msg in _messages(errors))

    validator._collect_derived_fields(
        RawDemand.from_raw({"fields": {"bad": []}}),
        errors,
        field_defs,
        defs_by_id,
        alias_index,
        derived_fields_with_deps,
    )
    assert any("Field 'bad' must be a dictionary" in msg for msg in _messages(errors))

    validator._collect_derived_fields(
        RawDemand.from_raw({"fields": {"calc": {"field": "id"}}}),
        errors,
        field_defs,
        defs_by_id,
        alias_index,
        derived_fields_with_deps,
    )
    assert any("must declare compute/call_by" in msg for msg in _messages(errors))

    validator._collect_derived_fields(
        RawDemand.from_raw({"fields": {"ok": {"compute": "1"}}}),
        errors,
        field_defs,
        defs_by_id,
        alias_index,
        derived_fields_with_deps,
    )
    assert any(item[0] == "ok" and item[1] == [] for item in derived_fields_with_deps)


def test_validator_derived_dependency_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    field_defs = {
        "dup": [_field_def("dup", source_id="a"), _field_def("dup", source_id="b")],
    }
    derived = [("calc", ["dup"], "fields.calc.compute")]
    validator._validate_derived_dependencies(derived, field_defs, errors)
    assert any("ambiguous" in msg for msg in _messages(errors))

    deps, dep_path = validator._resolve_derived_dependencies(field_id="calc", field_dict={"compute": ""})
    assert deps == []
    assert dep_path == "fields.calc"


def test_validator_collect_field_data_key_map_skips_blank_field_ids() -> None:
    validator = validator_module.ConfigValidator()
    out = validator._collect_field_data_key_map({None: {"extract": "id"}, "": {"extract": "id"}, " ok ": {"extract": "id"}})
    assert out == {"id": {"ok"}}


def test_validator_rejects_field_id_data_key_naming_conflict() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {
                "category_id": {"extract": "category_id_v2"},
                "product_category_id": {"extract": "category_id"},
            },
        },
        "sources": {},
    }

    _assert_validation_errors(config, "field_id/data_key naming conflict")


def test_validator_rejects_field_id_data_key_naming_conflict_in_source() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {
                "order_id": {"extract": "order_id"},
            },
        },
        "sources": {
            "products": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "product_id",
                "fields": {
                    "category_id": {"extract": "category_id_v2"},
                    "product_category_id": {"extract": "category_id"},
                },
            },
        },
    }

    _assert_validation_errors(config, "field_id/data_key naming conflict")


def test_validator_relation_steps_rejects_source_data_key_when_field_id_is_aliased() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {
                "category_id": {"extract": "category_id"},
            },
        },
        "sources": {
            "products": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "product_id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    # field_id != data_key
                    "product_category_id": {"extract": "category_id"},
                },
            },
        },
        "relations": {
            "orders_to_products": {
                "steps": [
                    # use data_key in steps (products.category_id), not field_id (products.product_category_id)
                    {"from": "orders.category_id", "to": "products.category_id"},
                ],
            },
        },
    }

    _assert_validation_errors(config, "relation steps must use field_id", "products.category_id")


def test_validator_relation_steps_reject_unknown_source_field_name() -> None:
    config = {
        "name": "demo",
        "main_source": {
            "source_id": "orders",
            "loader": "tests.fixtures.mock_loaders.mock_loader",
            "fields": {
                "category_id": {"extract": "category_id"},
            },
        },
        "sources": {
            "products": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "product_id",
                "bind": {"use_keys": {"param": "ids"}},
                "fields": {
                    "product_category_id": {"extract": "category_id"},
                },
            },
        },
        "relations": {
            "orders_to_products": {
                "steps": [
                    {"from": "orders.category_id", "to": "products.unknown_field"},
                ],
            },
        },
    }

    _assert_validation_errors(config, "references unknown field 'products.unknown_field'")


def test_validator_source_field_id_data_key_conflicts_ignores_missing_source_id() -> None:
    validator = validator_module.ConfigValidator()
    errors = []

    validator._validate_source_field_id_data_key_conflicts(
        [_field_def("id", source_id=None)],
        errors,
        main_source_id="orders",
    )

    assert not errors


def test_validator_collect_declared_field_names_ignores_empty_field_id() -> None:
    validator = validator_module.ConfigValidator()
    names = validator._collect_declared_field_names({"": {"field": "id"}, "ok": {"field": "id"}})

    assert "" not in names
    assert "ok" in names


def test_validator_collect_step_allowed_fields_handles_non_dict_main_source() -> None:
    validator = validator_module.ConfigValidator()

    allowed = validator._collect_step_allowed_fields({"main_source": []}, "orders")

    assert allowed.get("orders") == set()


def test_validator_derived_field_errors() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    validator._validate_derived_field("calc", {}, errors)
    assert any("must declare" in msg for msg in _messages(errors))

    errors = []
    validator._validate_derived_field("calc", {"compute": 1}, errors)
    assert any("compute must be a string" in msg for msg in _messages(errors))

    errors = []
    validator._validate_derived_field("calc", {"compute": ""}, errors)
    assert any("compute must not be empty" in msg for msg in _messages(errors))


def test_validator_source_field_edges() -> None:
    validator = validator_module.ConfigValidator()

    errors = []
    validator._validate_source_field("f", {}, set(), {}, "orders", {}, errors)
    assert any("missing required 'source'" in msg for msg in _messages(errors))

    errors = []
    validator._validate_source_field("f", {"extract": 1, "source": "orders"}, {"orders"}, {}, "orders", {}, errors)
    assert any("invalid extract" in msg for msg in _messages(errors))

    errors = []
    validator._validate_source_field("f", {"extract": "id", "source": "missing"}, {"orders"}, {}, "orders", {}, errors)
    assert any("references unknown source" in msg for msg in _messages(errors))


def test_validator_resolve_source_id_edges() -> None:
    validator = validator_module.ConfigValidator()

    errors = []
    assert validator._resolve_source_id_for_field("f", {}, None, errors, "fields.f") is None
    assert any("missing required 'source'" in msg for msg in _messages(errors))

    errors = []
    assert validator._resolve_source_id_for_field("f", {"source": 1}, None, errors, "fields.f") is None
    assert any("invalid source" in msg for msg in _messages(errors))

    errors = []
    assert validator._resolve_source_id_for_field("f", {"source": 1}, "orders", errors, "fields.f") is None
    assert any("invalid source" in msg for msg in _messages(errors))

    errors = []
    assert validator._resolve_source_id_for_field("f", {"source": "other"}, "orders", errors, "fields.f") is None
    assert any("does not match container source" in msg for msg in _messages(errors))


def test_validator_source_field_name_errors() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    assert validator._validate_source_field_name("f", {"field": 1}, errors, "fields.f") is False
    assert any("Legacy source field" in msg for msg in _messages(errors))


def test_validator_steps_binding_and_relation_path_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    validator._validate_steps_binding_requirements([("orders", "missing", False)], {}, errors, "ctx")

    errors = []
    validator._validate_relation_path("f", "orders", "orders", [], errors, "fields.f")
    assert any("steps is empty" in msg for msg in _messages(errors))

    errors = []
    validator._validate_relation_path("f", "customers", "orders", [("wrong", "customers", False)], errors, "fields.f")
    assert any("must start from main_source" in msg for msg in _messages(errors))

    errors = []
    validator._validate_relation_path("f", "customers", "orders", [("orders", "other", False)], errors, "fields.f")
    assert any("must end at source" in msg for msg in _messages(errors))


def test_validator_relations_edges() -> None:
    validator = validator_module.ConfigValidator()
    errors = []
    validator._validate_relations({"relations": []}, errors, {}, "orders")
    assert any("relations" in msg for msg in _messages(errors))

    errors = []
    validator._validate_relations(
        {"relations": {"r0": {"steps": [{"from": "orders.id", "to": "missing.id"}]}}},
        errors,
        {},
        "orders",
    )

    errors = []
    validator._validate_relations({"relations": {"r1": []}}, errors, {}, "orders")
    assert any("Relation 'r1' must be a dictionary" in msg for msg in _messages(errors))

    errors = []
    sources_info = {"customers": {"preload": False}}
    validator._validate_relations(
        {
            "relations": {
                "r1": {"steps": [{"from": "orders.id", "to": "customers.id"}]},
            }
        },
        errors,
        sources_info,
        "orders",
    )
    assert not errors


def test_validator_allows_main_source_relation_from_derived_field_but_rejects_to_side() -> None:
    validator = validator_module.ConfigValidator()
    validator._step_allowed_fields_by_source = {"orders": {"id"}, "customers": {"id"}}

    errors = []
    validator._validate_relations(
        {
            "fields": {"_broadcast_key": {"compute": "1"}},
            "relations": {"r1": {"steps": [{"from": "orders._broadcast_key", "to": "customers.id"}]}},
        },
        errors,
        {"customers": {"preload": False}},
        "orders",
    )
    assert not errors

    errors = []
    validator._step_allowed_fields_by_source = {"orders": {"id"}}
    validator._validate_steps(
        [{"from": "orders.id", "to": "orders._broadcast_key"}],
        {"orders"},
        errors,
        "ctx",
        main_source_id="orders",
        derived_field_ids=set(["_broadcast_key"]),
    )
    assert any("references unknown field" in msg for msg in _messages(errors))


def test_validator_steps_edges() -> None:
    validator = validator_module.ConfigValidator()

    errors = []
    validator._validate_steps("bad", {"orders"}, errors, "ctx")
    assert any("steps must be a list" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps([], {"orders"}, errors, "ctx")
    assert any("steps must not be empty" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps(["bad"], {"orders"}, errors, "ctx")
    assert any("steps[0] must be a dictionary" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps([{"from": "orders.id"}], {"orders"}, errors, "ctx")
    assert any("missing 'from' or 'to'" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps([{"from": "bad", "to": "orders.id"}], {"orders"}, errors, "ctx")
    assert any("from/to must be source.field or list" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps([{"from": "bad.id", "to": "missing.id"}], {"orders"}, errors, "ctx")
    assert any("references unknown source" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps(
        [{"from": ["orders.a", "orders.b"], "to": ["orders.a"]}],
        {"orders"},
        errors,
        "ctx",
    )
    assert any("field length mismatch" in msg for msg in _messages(errors))

    errors = []
    validator._validate_steps(
        [
            {"from": "orders.a", "to": "s1.a"},
            {"from": "orders.b", "to": "s2.b"},
        ],
        {"orders", "s1", "s2"},
        errors,
        "ctx",
    )
    assert any("breaks chain" in msg for msg in _messages(errors))


def test_validator_step_field_name_check_skips_missing_allowed_index() -> None:
    validator = validator_module.ConfigValidator()
    validator._step_allowed_fields_by_source = {"orders": {"id"}}
    errors = []

    validator._validate_steps([{"from": "orders.id", "to": "customers.customer_id"}], {"orders", "customers"}, errors, "ctx")

    assert not errors


def test_validator_bind_and_parse_helpers() -> None:
    validator = validator_module.ConfigValidator()
    config = {
        "name": "demo",
        "main_source": {"source_id": "orders", "loader": "tests.fixtures.mock_loaders.mock_loader"},
        "sources": {
            "s1": {
                "loader": "tests.fixtures.mock_loaders.mock_loader",
                "key": "id",
                "bind": "bad",
            }
        },
    }
    with pytest.raises(validator_module.ScalimConfigValidationError) as exc:
        validator.validate(config)
    assert any("Legacy YAML syntax is not supported: 'sources.s1.bind'" in msg for msg in exc.value.errors)

    assert validator._parse_source_field_expr(123) is None
    assert validator._parse_source_field_expr("bad") is None
    assert validator._parse_source_field_expr(_WeirdStr("orders.id")) is None
    assert validator._parse_source_field_expr(".field") is None

    assert validator._parse_source_field_group("bad") is None
    assert validator._parse_source_field_group(["orders.a", "bad"]) is None
    assert validator._parse_source_field_group(["orders.a", "other.a"]) is None


def test_validator_count_paths_and_loader_ref_edges() -> None:
    validator = validator_module.ConfigValidator()
    assert validator._count_paths("", "orders", {}) == 0

    relation_paths = {
        "r1": [("a", "b", False)],
        "r2": [("b", "a", False)],
    }
    assert validator._count_paths("a", "c", relation_paths) == 0

    assert validator._is_valid_loader_ref("") is False
    assert validator._is_valid_loader_ref(":attr") is False


def test_validation_report_from_errors_collects_issues() -> None:
    issue = validator_module.ValidationIssue(severity="error", message="boom", path="fields.id")
    report = validator_module.ValidationReport.from_errors([issue, "plain"])

    assert len(report.issues) == 2
    assert any(item.message == "boom" for item in report.issues)
    assert any(item.message == "plain" for item in report.issues)
