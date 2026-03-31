import pytest

from scalim.dsl.by_yaml._internal.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml._internal.config_parsing.models import AliasIndex, FieldDef, FieldDefIndex, RawDemand
from scalim.dsl.by_yaml._internal.config_parsing.parsers.outputs import _resolve_output_targets_from_inheritance
from scalim.dsl.by_yaml._internal.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError
from scalim.dsl.by_yaml.schema_dsl.models import (
    OutputAggregateConfig,
    OutputAggregateFieldConfig,
    OutputTargetConfig,
    OutputToConfig,
)


def _dummy_field_index() -> FieldDefIndex:
    return FieldDefIndex(field_defs=[], defs_by_id={}, alias_index=AliasIndex())


def test_validate_output_name_requires_value_and_pattern() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(ValueError, match=r"outputs\.\*\.name is required"):
        loader._validate_output_name("", path="outputs.*.name")
    with pytest.raises(ValueError, match="is invalid; expected identifier"):
        loader._validate_output_name("1bad", path="outputs.*.name")


def test_parse_outputs_rejects_non_list_and_non_object_items() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()

    raw = RawDemand.from_raw({"outputs": {}})
    with pytest.raises(TypeError, match="outputs must be a list"):
        loader._parse_outputs(raw, field_def_index=field_index)

    raw = RawDemand.from_raw({"outputs": [1]})
    with pytest.raises(TypeError, match=r"outputs\.0 must be an object"):
        loader._parse_outputs(raw, field_def_index=field_index)


def test_resolve_output_targets_from_inheritance_cycle_is_deterministic_and_has_name() -> None:
    base_outputs = [
        OutputTargetConfig(name="a", from_="b"),
        OutputTargetConfig(name="b", from_="a"),
    ]
    with pytest.raises(ValueError, match=r"cycle at 'a'"):
        _ = _resolve_output_targets_from_inheritance(base_outputs, validate_output_name=lambda _x: None)  # noqa: SLF001


def test_resolve_output_targets_from_inheritance_rejects_unknown_from_with_names() -> None:
    base_outputs = [
        OutputTargetConfig(name="child", from_="missing"),
    ]
    with pytest.raises(ValueError, match=r"outputs\.child\.from points to unknown output: missing"):
        _ = _resolve_output_targets_from_inheritance(base_outputs, validate_output_name=lambda _x: None)  # noqa: SLF001


def test_resolve_output_targets_from_inheritance_rejects_inherit_fields_when_base_has_none() -> None:
    base_outputs = [
        OutputTargetConfig(name="base_agg", aggregate=OutputAggregateConfig()),
        OutputTargetConfig(name="child_detail", from_="base_agg"),
    ]
    with pytest.raises(ValueError, match=r"inherits fields from 'base_agg'"):
        _ = _resolve_output_targets_from_inheritance(base_outputs, validate_output_name=lambda _x: None)  # noqa: SLF001


def test_parse_output_target_rejects_fields_non_list() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()
    field_index = _dummy_field_index()

    raw_target = {
        "name": "detail",
        "to": {"file": "detail_csv"},
        "fields": "order_id",
    }

    with pytest.raises(TypeError, match=r"outputs\.0\.fields must be a list"):
        loader._parse_output_target(
            raw_target,
            idx=0,
            outputs_key="outputs",
            field_def_index=field_index,
            known_field_ids={"order_id"},
            engine=engine,
        )


def test_resolve_output_field_ref_rejects_non_str_and_non_mapping() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()

    with pytest.raises(TypeError, match=r"outputs\.0\.fields\.0 must be field_id string"):
        _ = loader._resolve_output_field_ref(  # type: ignore[attr-defined]
            1,
            outputs_key="outputs",
            output_idx=0,
            field_path="0",
            field_def_index=field_index,
        )


def test_resolve_output_field_ref_rejects_unresolvable_object() -> None:
    loader = YamlDemandLoader()
    field_defs = [
        FieldDef(field_id="order_id", kind="source", data={"extract": "order_id"}, source_id="orders"),
    ]
    field_index = FieldDefIndex(field_defs=field_defs, defs_by_id={"order_id": field_defs}, alias_index=AliasIndex())

    with pytest.raises(ValueError, match=r"outputs\.0\.fields\.0 cannot resolve object to a unique field_id"):
        _ = loader._resolve_output_field_ref(  # type: ignore[attr-defined]
            {"extract": "missing"},
            outputs_key="outputs",
            output_idx=0,
            field_path="0",
            field_def_index=field_index,
        )


def test_resolve_output_field_ref_rejects_ambiguous_content_match() -> None:
    loader = YamlDemandLoader()
    field_defs = [
        FieldDef(field_id="a", kind="source", data={"extract": "id"}, source_id="orders"),
        FieldDef(field_id="b", kind="source", data={"extract": "id"}, source_id="orders"),
    ]
    field_index = FieldDefIndex(field_defs=field_defs, defs_by_id={"a": [field_defs[0]], "b": [field_defs[1]]}, alias_index=AliasIndex())

    with pytest.raises(ValueError, match=r"outputs\.0\.fields\.0 is ambiguous; object matches multiple field_id values"):
        _ = loader._resolve_output_field_ref(  # type: ignore[attr-defined]
            {"extract": "id"},
            outputs_key="outputs",
            output_idx=0,
            field_path="0",
            field_def_index=field_index,
        )


def test_aggregate_derived_deps_unknown_producer_key_falls_back_to_empty_tuple() -> None:
    loader = YamlDemandLoader()
    cfg = OutputAggregateFieldConfig(producer_key="unknown", config={})
    assert loader._derived_deps_for_aggregate_derived_field(cfg) == ()  # type: ignore[attr-defined]


def test_build_aggregate_field_index_skips_non_dict_values() -> None:
    loader = YamlDemandLoader()

    idx = loader._build_aggregate_field_index({"bad": 1, "ok": {"count": {}}})  # type: ignore[arg-type]
    assert [fd.out_field_id for fd in idx.field_defs] == ["ok"]


def test_parse_output_aggregate_field_rejects_non_str_name() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()
    agg_field_index = loader._build_aggregate_field_index({})
    engine = SecureComputeEngine()

    with pytest.raises(TypeError, match=r"aggregate\.fields\.cnt\.name must be a string"):
        _ = loader._parse_output_aggregate_field(  # type: ignore[attr-defined]
            {"name": 1, "count": {}},
            base_path="aggregate.fields.cnt",
            field_def_index=field_index,
            agg_field_index=agg_field_index,
            engine=engine,
        )


def test_parse_output_aggregate_field_agg_allows_null_field_value() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()

    cfg = loader._parse_output_aggregate_field_agg(  # type: ignore[attr-defined]
        "count",
        {"field": None},
        base_path="aggregate.fields.cnt",
        field_def_index=field_index,
    )
    assert cfg == {"field": None}


def test_parse_output_aggregate_field_rank_rejects_blank_by_after_strip() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()
    agg_field_index = loader._build_aggregate_field_index({})

    with pytest.raises(ValueError, match=r"aggregate\.fields\.r\.rank\.by is required"):
        _ = loader._parse_output_aggregate_field_rank(  # type: ignore[attr-defined]
            "rank",
            {"by": "  "},
            base_path="aggregate.fields.r",
            field_def_index=field_index,
            agg_field_index=agg_field_index,
        )


def test_validate_outputs_semantics_rejects_empty_aggregate_output_fields() -> None:
    loader = YamlDemandLoader()

    agg = OutputAggregateConfig(
        group_by=("a",),
        fields={"cnt": OutputAggregateFieldConfig(producer_key="count", config={})},
    )
    out = OutputTargetConfig(
        name="by_a",
        to=OutputToConfig(file="detail_csv"),
        fields=(),
        aggregate=agg,
    )

    with pytest.raises(ValueError, match=r"outputs\.by_a\.fields must not be empty"):
        loader._validate_outputs_semantics([out], known_field_ids={"a"})  # type: ignore[arg-type]


def test_parse_output_target_rejects_legacy_container_migration_hint() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()
    field_index = _dummy_field_index()

    with pytest.raises(ValueError, match=r"outputs\.0\.container was removed"):
        loader._parse_output_target(
            {"name": "detail", "container": {"type": "csv", "path": "./out.csv"}, "fields": ["order_id"]},
            idx=0,
            outputs_key="outputs",
            field_def_index=field_index,
            known_field_ids={"order_id"},
            engine=engine,
        )


def test_parse_output_aggregate_defensive_checks() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()
    engine = SecureComputeEngine()

    with pytest.raises(TypeError, match=r"aggregate\.group_by must be a list"):
        _ = loader._parse_output_aggregate(
            {"group_by": "order_id", "fields": {"cnt": {"count": {}}}},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"aggregate\.fields must be an object"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "fields": 1},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"aggregate\.metrics was removed; use aggregate\.fields"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"max_groups must be >= 0"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "fields": {"cnt": {"count": {}}}, "max_groups": -1},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"max_distinct must be >= 0"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "fields": {"cnt": {"count": {}}}, "max_distinct": -1},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"distinct_on_overflow='bad' is invalid"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "fields": {"cnt": {"count": {}}}, "distinct_on_overflow": "bad"},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"aggregate\.rank_by was removed"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "fields": {"cnt": {"count": {}}}, "rank_by": "cnt"},
            base_path="aggregate",
            field_def_index=field_index,
            engine=engine,
        )

    parsed = loader._parse_output_aggregate(
        {"group_by": ["order_id"], "fields": {"": {"count": {}}, "cnt": {"count": {}}}},
        base_path="aggregate",
        field_def_index=field_index,
        engine=engine,
    )
    assert parsed.fields
    assert "cnt" in parsed.fields
    assert "" not in parsed.fields


def test_parse_output_aggregate_field_defensive_checks() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()
    agg_index = loader._build_aggregate_field_index({})
    engine = SecureComputeEngine()

    with pytest.raises(TypeError, match=r"agg\.fields\.x must be an object"):
        _ = loader._parse_output_aggregate_field(  # type: ignore[arg-type]
            1,
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"must contain exactly 1 producer key"):
        _ = loader._parse_output_aggregate_field(
            {"count": {}, "sum": {"field": "v"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"unknown producer key"):
        _ = loader._parse_output_aggregate_field(
            {"bad": {}}, base_path="agg.fields.x", field_def_index=field_index, agg_field_index=agg_index, engine=engine
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.sum must be an object"):
        _ = loader._parse_output_aggregate_field(
            {"sum": 1},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.sum\.field is required"):
        _ = loader._parse_output_aggregate_field(
            {"sum": {}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.by is required"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.call_by must be a string"):
        _ = loader._parse_output_aggregate_field(
            {"call_by": {}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.call_by must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"call_by": "   "},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.call_by is invalid"):
        _ = loader._parse_output_aggregate_field(
            {"call_by": "bad"},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.compute must be a string"):
        _ = loader._parse_output_aggregate_field(
            {"compute": {}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.compute must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"compute": "   "},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.compute is invalid"):
        _ = loader._parse_output_aggregate_field(
            {"compute": "a +"},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"   ": {}}, base_path="agg.fields.x", field_def_index=field_index, agg_field_index=agg_index, engine=engine
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.count has unknown keys: bad"):
        _ = loader._parse_output_aggregate_field(
            {"count": {"bad": 1}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.count_distinct\.fields must be a list"):
        _ = loader._parse_output_aggregate_field(
            {"count_distinct": {"fields": "a"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.count_true_gte\.threshold is required"):
        _ = loader._parse_output_aggregate_field(
            {"count_true_gte": {"field": "v"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.count_distinct does not allow both field and fields"):
        _ = loader._parse_output_aggregate_field(
            {"count_distinct": {"field": "a", "fields": ["b"]}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.count_distinct requires field or fields"):
        _ = loader._parse_output_aggregate_field(
            {"count_distinct": {}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.count_distinct\.fields must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"count_distinct": {"field": "a", "fields": []}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.rank must be an object"):
        _ = loader._parse_output_aggregate_field(  # type: ignore[arg-type]
            {"rank": 1},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank has unknown keys: bad"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "bad": 1}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.rank\.partition_by must be a list"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "partition_by": "a"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.partition_by must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "partition_by": [" "]}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.order='bad' is invalid"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "order": "bad"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.rank\.order_by must be a list"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "order_by": "a"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.order_by must not be empty"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "order_by": [" "]}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.top_k must be >= 0"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "top_k": -1}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.rank\.top_k_mode='bad' is invalid"):
        _ = loader._parse_output_aggregate_field(
            {"rank": {"by": "cnt", "top_k_mode": "bad"}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(TypeError, match=r"agg\.fields\.x\.score_by_rank must be an object"):
        _ = loader._parse_output_aggregate_field(
            {"score_by_rank": "x"},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"agg\.fields\.x\.score_by_rank has unknown keys: bad"):
        _ = loader._parse_output_aggregate_field(
            {"score_by_rank": {"bad": 1}},
            base_path="agg.fields.x",
            field_def_index=field_index,
            agg_field_index=agg_index,
            engine=engine,
        )

    parsed = loader._parse_output_aggregate_field(
        {
            "rank": {
                "by": "cnt",
                "partition_by": ["g"],
                "order_by": ["cnt", "g"],
            }
        },
        base_path="agg.fields.x",
        field_def_index=field_index,
        agg_field_index=agg_index,
        engine=engine,
    )
    assert parsed.producer_key == "rank"
    assert parsed.config["partition_by"] == ("g",)
    assert parsed.config["order_by"] == ("cnt", "g")


def test_parse_output_aggregate_supports_object_alias_field_refs_and_agg_field_refs() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()

    group_def = {"extract": "group"}
    amount_def = {"extract": "amount"}

    group_fd = FieldDef(field_id="group", kind="source", data=group_def, source_id="orders")
    amount_fd = FieldDef(field_id="amount", kind="source", data=amount_def, source_id="orders")

    alias_index = AliasIndex()
    alias_index.add(group_def, group_fd)
    alias_index.add(amount_def, amount_fd)

    field_index = FieldDefIndex(
        field_defs=[group_fd, amount_fd],
        defs_by_id={"group": [group_fd], "amount": [amount_fd]},
        alias_index=alias_index,
    )

    cnt_def = {"count": {"field": amount_def}}
    distinct_def = {"count_distinct": {"fields": [[group_def, amount_def]]}}
    rank_def = {"dense_rank": {"by": cnt_def, "order_by": [cnt_def]}}
    score_def = {"score_by_rank": {"rank_field": rank_def, "base": 100, "step": 3}}

    parsed = loader._parse_output_aggregate(
        {
            "group_by": [[group_def]],
            "fields": {
                "cnt": cnt_def,
                "distinct": distinct_def,
                "rank": rank_def,
                "score": score_def,
            },
        },
        base_path="agg",
        field_def_index=field_index,
        engine=engine,
    )

    assert parsed.group_by == ("group",)
    assert parsed.fields["cnt"].producer_key == "count"
    assert parsed.fields["cnt"].config["field"] == "amount"
    assert parsed.fields["distinct"].producer_key == "count_distinct"
    assert parsed.fields["distinct"].config["fields"] == ("group", "amount")
    assert parsed.fields["rank"].producer_key == "dense_rank"
    assert parsed.fields["rank"].config["by"] == "cnt"
    assert parsed.fields["rank"].config["order_by"] == ("cnt",)
    assert parsed.fields["score"].producer_key == "score_by_rank"
    assert parsed.fields["score"].config["rank_field"] == "rank"


def test_parse_where_requires_defensive_blank_and_errors() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()

    deps = loader._parse_where_requires(
        "   ",
        output_name="detail",
        known_field_ids={"channel"},
        engine=engine,
        path="outputs.0.where",
    )
    assert deps == ()

    with pytest.raises(ValueError, match=r"depends on unknown fields"):
        loader._parse_where_requires(
            "missing == 1",
            output_name="detail",
            known_field_ids={"channel"},
            engine=engine,
            path="outputs.0.where",
        )

    with pytest.raises(ValueError, match=r"Invalid where expression"):
        loader._parse_where_requires(
            "channel ==",
            output_name="detail",
            known_field_ids={"channel"},
            engine=engine,
            path="outputs.0.where",
        )


def test_validate_outputs_semantics_defensive_aggregate_constraints() -> None:
    loader = YamlDemandLoader()
    to_cfg = OutputToConfig(file="detail_csv")

    def _detail() -> OutputTargetConfig:
        return OutputTargetConfig(name="detail", to=to_cfg, fields=("order_id",))

    # aggregate.group_by empty
    agg = OutputAggregateConfig(group_by=(), fields={"cnt": OutputAggregateFieldConfig(producer_key="count", config={})})
    with pytest.raises(ValueError, match=r"aggregate\.group_by cannot be empty"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    # aggregate.fields empty
    agg = OutputAggregateConfig(group_by=("order_id",), fields={})
    with pytest.raises(ValueError, match=r"aggregate\.fields cannot be empty"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    # overlap between group_by and metric ids
    agg = OutputAggregateConfig(group_by=("dup",), fields={"dup": OutputAggregateFieldConfig(producer_key="count", config={})})
    with pytest.raises(ValueError, match=r"fields ids conflict with group_by"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"dup"})

    # group_by unknown
    agg = OutputAggregateConfig(group_by=("missing",), fields={"cnt": OutputAggregateFieldConfig(producer_key="count", config={})})
    with pytest.raises(ValueError, match=r"group_by reference unknown fields"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids=set())

    # agg metric reference unknown input fields
    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "sum_amount": OutputAggregateFieldConfig(producer_key="sum", config={"field": "missing"}),
        },
    )
    with pytest.raises(ValueError, match=r"fields reference unknown input fields"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    # rank.by must be group_by field or agg metric id
    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "bad",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"by='bad'"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": ("missing",),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"partition_by must be a subset of group_by"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 1,
                    "top_k_mode": "rows",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"top_k_mode='rows' requires order_by"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": ("cnt",),
                    "top_k": 1,
                    "top_k_mode": "rows",
                },
            ),
            "score": OutputAggregateFieldConfig(
                producer_key="score_by_rank",
                config={"rank_field": "missing"},
            ),
        },
    )
    with pytest.raises(ValueError, match=r"score_by_rank rank_field='missing'"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": ("cnt",),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
            "score": OutputAggregateFieldConfig(
                producer_key="call_by",
                config="pkg.mod:fn(x=missing)",
            ),
        },
    )
    with pytest.raises(ValueError, match=r"call_by reference unknown fields"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    # workbook share loop: len(names) <= 1 path should short-circuit (covers `continue`)
    loader._validate_outputs_semantics([_detail()], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "order_id",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"must include at least one aggregation function field"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "rank": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": ("missing",),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"order_by reference unknown agg output fields"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})

    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "r1": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 1,
                    "top_k_mode": "rank",
                },
            ),
            "r2": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "cnt",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 1,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    with pytest.raises(ValueError, match=r"supports top_k on at most one rank field"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)], known_field_ids={"order_id"})


def test_validate_outputs_semantics_allows_aggregate_dag_rank_by_compute_post_depends_on_post_and_rank_after_post() -> None:
    loader = YamlDemandLoader()
    to_cfg = OutputToConfig(file="detail_csv")

    agg = OutputAggregateConfig(
        group_by=("g",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "ratio": OutputAggregateFieldConfig(
                producer_key="compute",
                config={"expression": "cnt + 1", "dependencies": ("cnt",)},
            ),
            "rank1": OutputAggregateFieldConfig(
                producer_key="dense_rank",
                config={
                    "by": "ratio",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": ("ratio",),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
            "score1": OutputAggregateFieldConfig(
                producer_key="score_by_rank",
                config={"rank_field": "rank1"},
            ),
            "total": OutputAggregateFieldConfig(
                producer_key="compute",
                config={"expression": "score1 + 1", "dependencies": ("score1",)},
            ),
            "rank2": OutputAggregateFieldConfig(
                producer_key="dense_rank",
                config={
                    "by": "total",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )

    loader._validate_outputs_semantics(
        [OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)],
        known_field_ids={"g"},
    )


def test_validate_outputs_semantics_rejects_compute_referencing_unknown_agg_fields() -> None:
    loader = YamlDemandLoader()
    to_cfg = OutputToConfig(file="detail_csv")

    agg = OutputAggregateConfig(
        group_by=("g",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "x": OutputAggregateFieldConfig(
                producer_key="compute",
                config={
                    "expression": "missing + 1",
                    "dependencies": ("missing",),
                },
            ),
        },
    )

    with pytest.raises(ValueError, match=r"compute reference unknown fields"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)],
            known_field_ids={"g"},
        )


def test_validate_outputs_semantics_aggregate_dag_cycle_detection_is_actionable() -> None:
    loader = YamlDemandLoader()
    to_cfg = OutputToConfig(file="detail_csv")

    agg = OutputAggregateConfig(
        group_by=("g",),
        fields={
            "cnt": OutputAggregateFieldConfig(producer_key="count", config={}),
            "a": OutputAggregateFieldConfig(
                producer_key="compute",
                config={"expression": "b + 1", "dependencies": ("b",)},
            ),
            "b": OutputAggregateFieldConfig(
                producer_key="compute",
                config={"expression": "a + 1", "dependencies": ("a",)},
            ),
        },
    )

    with pytest.raises(ValueError, match=r"cyclic dependency"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", to=to_cfg, aggregate=agg)],
            known_field_ids={"g"},
        )


def test_validate_outputs_semantics_allows_multiple_file_targets() -> None:
    loader = YamlDemandLoader()

    outputs = [
        OutputTargetConfig(
            name="a",
            to=OutputToConfig(file="a_csv"),
            fields=("order_id",),
        ),
        OutputTargetConfig(
            name="b",
            to=OutputToConfig(file="b_csv"),
            fields=("order_id",),
        ),
        OutputTargetConfig(
            name="c",
            to=OutputToConfig(file="c_csv"),
            fields=("order_id",),
        ),
    ]

    loader._validate_outputs_semantics(outputs, known_field_ids={"order_id"})


def test_collect_required_field_ids_from_aggregate_includes_fields_list() -> None:
    loader = YamlDemandLoader()
    agg = OutputAggregateConfig(
        group_by=("order_id",),
        fields={
            "distinct_users": OutputAggregateFieldConfig(producer_key="count_distinct", config={"fields": ("user_id", "device_id")}),
        },
    )
    required = loader._collect_required_field_ids_from_aggregate(agg)
    assert required == ["user_id", "device_id"]


def test_parse_outputs_from_inherits_fields_requires_base_fields() -> None:
    loader = YamlDemandLoader()
    field_index = _dummy_field_index()

    raw = RawDemand.from_raw({"outputs": [{"name": "base"}, {"name": "child", "from": "base"}]})
    with pytest.raises(ValueError, match=r"outputs\.child inherits fields from 'base', but base output has no fields"):
        loader._parse_outputs(raw, field_def_index=field_index)


def test_validate_outputs_semantics_rejects_legacy_container_migration_hint() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()
    field_index = _dummy_field_index()

    with pytest.raises(ValueError, match=r"outputs\.0\.container was removed"):
        loader._parse_output_target(
            {"name": "detail", "container": {"type": "workbook", "path": "./out.xlsx"}, "fields": ["order_id"]},
            idx=0,
            outputs_key="outputs",
            field_def_index=field_index,
            known_field_ids={"order_id"},
            engine=engine,
        )
