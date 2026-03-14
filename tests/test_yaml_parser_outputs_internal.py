import pytest

from scalim.dsl.by_yaml.config_parsing.loader import YamlDemandLoader
from scalim.dsl.by_yaml.config_parsing.models import AliasIndex, FieldDef, FieldDefIndex, RawDemand
from scalim.dsl.by_yaml.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.schema_dsl.models import (
    OutputAggregateConfig,
    OutputAggregateMetricConfig,
    OutputAggregateMetricConfig as MetricCfg,
    OutputContainerConfig,
    OutputTargetConfig,
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


def test_parse_output_target_rejects_fields_non_list() -> None:
    loader = YamlDemandLoader()
    engine = SecureComputeEngine()
    field_index = _dummy_field_index()

    raw_target = {
        "name": "detail",
        "container": {"type": "csv", "path": "./out.csv"},
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


@pytest.mark.parametrize(
    "raw,base_path,exc_type,match",
    [
        ({"path": "./out.csv"}, "outputs.0.container", ValueError, r"outputs\.0\.container\.type is required"),
        ({"type": "bad", "path": "./out.csv"}, "outputs.0.container", ValueError, r"type='bad' is invalid"),
        ({"type": "csv"}, "outputs.0.container", ValueError, r"path is required"),
        (
            {"type": "csv", "path": "./out.csv", "header_fields_output_by": "bad"},
            "outputs.0.container",
            ValueError,
            r"header_fields_output_by='bad' is invalid",
        ),
    ],
    ids=["missing-type", "bad-type", "missing-path", "bad-header-by"],
)
def test_parse_output_container_defensive_checks(raw, base_path, exc_type, match) -> None:
    loader = YamlDemandLoader()
    with pytest.raises(exc_type, match=match):
        _ = loader._parse_output_container(raw, base_path=base_path)


def test_parse_output_aggregate_defensive_checks() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match=r"aggregate\.group_by must be a list"):
        _ = loader._parse_output_aggregate({"group_by": "order_id", "metrics": {"cnt": {"op": "count"}}}, base_path="aggregate")

    with pytest.raises(TypeError, match=r"aggregate\.metrics must be an object"):
        _ = loader._parse_output_aggregate({"group_by": ["order_id"], "metrics": 1}, base_path="aggregate")

    # invalid metric entries are skipped defensively
    agg = loader._parse_output_aggregate({"group_by": ["order_id"], "metrics": {"": {"op": "count"}, "cnt": 1}}, base_path="aggregate")
    assert agg.metrics == {}

    with pytest.raises(ValueError, match=r"max_groups must be >= 0"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}, "max_groups": -1},
            base_path="aggregate",
        )

    with pytest.raises(ValueError, match=r"max_distinct must be >= 0"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}, "max_distinct": -1},
            base_path="aggregate",
        )

    with pytest.raises(ValueError, match=r"distinct_on_overflow='bad' is invalid"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}, "distinct_on_overflow": "bad"},
            base_path="aggregate",
        )

    with pytest.raises(ValueError, match=r"rank_order='bad' is invalid"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}, "rank_order": "bad"},
            base_path="aggregate",
        )

    with pytest.raises(ValueError, match=r"top_k must be >= 0"):
        _ = loader._parse_output_aggregate(
            {"group_by": ["order_id"], "metrics": {"cnt": {"op": "count"}}, "top_k": -1},
            base_path="aggregate",
        )


def test_parse_output_aggregate_metric_defensive_checks() -> None:
    loader = YamlDemandLoader()

    with pytest.raises(TypeError, match=r"metric\.fields must be a list"):
        _ = loader._parse_output_aggregate_metric({"op": "count_distinct", "fields": "user_id"}, base_path="metric")

    with pytest.raises(ValueError, match=r"metric\.op is required"):
        _ = loader._parse_output_aggregate_metric({}, base_path="metric")

    with pytest.raises(ValueError, match=r"op='bad' is invalid"):
        _ = loader._parse_output_aggregate_metric({"op": "bad"}, base_path="metric")

    with pytest.raises(ValueError, match=r"field is required for op='sum'"):
        _ = loader._parse_output_aggregate_metric({"op": "sum"}, base_path="metric")

    with pytest.raises(ValueError, match=r"threshold is required for op='count_true_gte'"):
        _ = loader._parse_output_aggregate_metric({"op": "count_true_gte", "field": "order_id"}, base_path="metric")

    with pytest.raises(ValueError, match=r"does not allow both field and fields"):
        _ = loader._parse_output_aggregate_metric({"op": "count_distinct", "field": "user_id", "fields": ["user_id"]}, base_path="metric")

    with pytest.raises(ValueError, match=r"requires field or fields"):
        _ = loader._parse_output_aggregate_metric({"op": "count_distinct"}, base_path="metric")

    # normalization of `fields`
    metric = loader._parse_output_aggregate_metric({"op": "count_distinct", "fields": ["user_id", ""]}, base_path="metric")
    assert metric.field_ids == ("user_id",)


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
    container = OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S")

    def _detail() -> OutputTargetConfig:
        return OutputTargetConfig(name="detail", container=container, fields=("order_id",))

    # aggregate.group_by empty
    agg = OutputAggregateConfig(group_by=(), metrics={"cnt": MetricCfg(op="count")})
    with pytest.raises(ValueError, match=r"aggregate\.group_by cannot be empty"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # aggregate.metrics empty
    agg = OutputAggregateConfig(group_by=("order_id",), metrics={})
    with pytest.raises(ValueError, match=r"aggregate\.metrics cannot be empty"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # overlap between group_by and metric ids
    agg = OutputAggregateConfig(group_by=("dup",), metrics={"dup": MetricCfg(op="count")})
    with pytest.raises(ValueError, match=r"metrics ids conflict with group_by"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"dup"})

    # rank_field_id conflicts with group_by
    agg = OutputAggregateConfig(group_by=("order_id",), metrics={"cnt": MetricCfg(op="count")}, rank_field_id="order_id")
    with pytest.raises(ValueError, match=r"rank_field_id conflicts with group_by"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # group_by unknown
    agg = OutputAggregateConfig(group_by=("missing",), metrics={"cnt": MetricCfg(op="count")})
    with pytest.raises(ValueError, match=r"group_by reference unknown fields"):
        loader._validate_outputs_semantics([OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids=set())

    # metrics reference unknown fields
    agg = OutputAggregateConfig(group_by=("order_id",), metrics={"sum_amount": MetricCfg(op="sum", field_id="missing")})
    with pytest.raises(ValueError, match=r"metrics reference unknown fields"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # rank_by must be group_by or metric ids
    agg = OutputAggregateConfig(group_by=("order_id",), metrics={"cnt": MetricCfg(op="count")}, rank_by="bad")
    with pytest.raises(ValueError, match=r"aggregate\.rank_by='bad'"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # rank_field_id conflicts with metrics id
    agg = OutputAggregateConfig(group_by=("order_id",), metrics={"rank": MetricCfg(op="count")}, rank_field_id="rank")
    with pytest.raises(ValueError, match=r"rank_field_id conflicts with metrics id"):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="agg", container=container, aggregate=agg)], known_field_ids={"order_id"}
        )

    # workbook share loop: len(names) <= 1 path should short-circuit (covers `continue`)
    loader._validate_outputs_semantics([_detail()], known_field_ids={"order_id"})


def test_validate_outputs_semantics_shared_workbook_loop_skips_non_workbook_targets() -> None:
    loader = YamlDemandLoader()

    outputs = [
        OutputTargetConfig(
            name="a",
            container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="A"),
            fields=("order_id",),
        ),
        OutputTargetConfig(
            name="b",
            container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="B"),
            fields=("order_id",),
        ),
        OutputTargetConfig(
            name="c",
            container=OutputContainerConfig(type="csv", path="./out.csv"),
            fields=("order_id",),
        ),
    ]

    loader._validate_outputs_semantics(outputs, known_field_ids={"order_id"})


def test_collect_required_field_ids_from_aggregate_includes_fields_list() -> None:
    loader = YamlDemandLoader()
    agg = OutputAggregateConfig(
        group_by=("order_id",),
        metrics={
            "distinct_users": OutputAggregateMetricConfig(op="count_distinct", field_ids=("user_id", "device_id")),
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


@pytest.mark.parametrize(
    "container_kwargs,match",
    [
        ({"sheet": "S"}, r"container\.sheet is only allowed for type=workbook"),
        ({"allow_formulas": True}, r"container\.allow_formulas is only allowed for type=workbook"),
        ({"write_lock": True}, r"container\.write_lock is only allowed for type=workbook"),
    ],
    ids=["csv-sheet", "csv-allow-formulas", "csv-write-lock"],
)
def test_validate_outputs_semantics_csv_disallows_workbook_only_options(container_kwargs, match) -> None:
    loader = YamlDemandLoader()

    container = OutputContainerConfig(type="csv", path="./out.csv", **container_kwargs)
    with pytest.raises(ValueError, match=match):
        loader._validate_outputs_semantics(
            [OutputTargetConfig(name="csv1", container=container, fields=("order_id",))],
            known_field_ids={"order_id"},
        )
