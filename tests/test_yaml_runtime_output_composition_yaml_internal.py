from decimal import Decimal

import pytest

from scalim.dsl.by_yaml.config_parsing.call_by import CallByValue
from scalim.dsl.by_yaml.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.runtime import output_composition_yaml as oc_yaml
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import (
    DemandConfig,
    OutputAggregateConfig,
    OutputAggregateFieldConfig,
    OutputContainerConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
)
from scalim.spec.ir.demand import DemandIr
from scalim.spec.ir.fields import FieldIr
from scalim.spec.ir.sources import MainSourceIr


def _dummy_main_loader(*_args, **_kwargs):  # type: ignore[no-untyped-def]
    return []


def _make_demand_ir(*, field_name_by_id=None) -> DemandIr:  # type: ignore[no-untyped-def]
    main = MainSourceIr(source_id="orders", loader=_dummy_main_loader)
    field_irs = []
    if field_name_by_id:
        for field_id, name in field_name_by_id.items():
            field_irs.append(FieldIr(field_id=field_id, name=name, source=main))
    return DemandIr.from_irs(sources=[], fields=field_irs, main_source=main, name="demo")


def _resolver() -> SecurePythonReferenceResolver:
    return SecurePythonReferenceResolver(allowed_modules=frozenset(["scalim"]))


def _tests_resolver() -> SecurePythonReferenceResolver:
    return SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.call_by_fns"]))


def test_export_layout_for_derived_field_id_header_has_no_header_names() -> None:
    demand_ir = _make_demand_ir(field_name_by_id={"a": "A"})

    layout = oc_yaml._export_layout_for_derived(  # noqa: SLF001
        demand_ir=demand_ir,
        agg=OutputAggregateConfig(group_by=(), fields={}),
        field_ids=["a"],
        header_fields_output_by="field_id",
    )
    assert layout.field_ids == ("a",)
    assert layout.header_names is None


def test_export_layout_for_derived_name_header_without_diffs_has_no_header_names() -> None:
    demand_ir = _make_demand_ir(field_name_by_id={"a": "a"})

    layout = oc_yaml._export_layout_for_derived(  # noqa: SLF001
        demand_ir=demand_ir,
        agg=OutputAggregateConfig(group_by=(), fields={}),
        field_ids=["a"],
        header_fields_output_by="name",
    )
    assert layout.field_ids == ("a",)
    assert layout.header_names is None


def test_compile_where_predicate_executes_expression() -> None:
    engine = SecureComputeEngine()

    predicate = oc_yaml._compile_where_predicate(  # noqa: SLF001
        engine=engine,
        expression="channel == 'direct'",
        requires=("channel",),
    )
    assert predicate({"channel": "direct"}) is True
    assert predicate({"channel": "other"}) is False


def test_derived_output_layout_fields_includes_rank_field() -> None:
    agg = OutputAggregateConfig(
        group_by=("a",),
        fields={
            "m": OutputAggregateFieldConfig(producer_key="count", config={}),
            "r": OutputAggregateFieldConfig(
                producer_key="rank",
                config={
                    "by": "m",
                    "partition_by": (),
                    "order": "desc",
                    "order_by": (),
                    "top_k": 0,
                    "top_k_mode": "rank",
                },
            ),
        },
    )
    assert oc_yaml._derived_output_layout_fields(agg) == ("a", "m", "r")  # noqa: SLF001


def test_compile_extra_sheet_requires_workbook_path() -> None:
    with pytest.raises(ValueError, match=r"meta requires a workbook path"):
        _ = oc_yaml._compile_extra_sheet(  # noqa: SLF001
            target_id="meta",
            cfg=OutputExtraSheetConfig(),
            default_sheet="__meta__",
            default_workbook_container=None,
        )


def test_first_workbook_container_skips_none_container() -> None:
    outputs = (
        OutputTargetConfig(name="a", container=None),
        OutputTargetConfig(name="b", container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S")),
    )

    container = oc_yaml._first_workbook_container(outputs)  # noqa: SLF001
    assert container is not None
    assert container.type == "workbook"
    assert container.path == "./out.xlsx"


def test_compile_output_composition_meta_audit_requires_outputs() -> None:
    config = DemandConfig(meta=OutputExtraSheetConfig())

    with pytest.raises(ValueError, match=r"meta/audit requires outputs"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_returns_none_when_no_outputs() -> None:
    assert oc_yaml.compile_output_composition_from_yaml(DemandConfig(), _make_demand_ir(), resolver=_resolver()) is None


def test_compile_output_composition_meta_output_name_is_reserved() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="meta",
                container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S"),
                fields=("a",),
            ),
        ),
        meta=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'meta'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_audit_output_name_is_reserved() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="audit",
                container=OutputContainerConfig(type="workbook", path="./out.xlsx", sheet="S"),
                fields=("a",),
            ),
        ),
        audit=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'audit'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_requires_container() -> None:
    config = DemandConfig(outputs=(OutputTargetConfig(name="detail", container=None, fields=("a",)),))

    with pytest.raises(ValueError, match=r"outputs\.detail missing container"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_to_decimal_handles_common_types_and_error_branches() -> None:
    assert oc_yaml._to_decimal(None) is None  # noqa: SLF001
    assert oc_yaml._to_decimal(Decimal("1.5")) == Decimal("1.5")  # noqa: SLF001
    assert oc_yaml._to_decimal(True) == Decimal("1")  # noqa: SLF001
    assert oc_yaml._to_decimal(False) == Decimal("0")  # noqa: SLF001
    assert oc_yaml._to_decimal(2) == Decimal("2")  # noqa: SLF001
    assert oc_yaml._to_decimal(0.1) == Decimal("0.1")  # noqa: SLF001
    assert oc_yaml._to_decimal(" 1.50 ") == Decimal("1.50")  # noqa: SLF001
    assert oc_yaml._to_decimal(" ") is None  # noqa: SLF001
    assert oc_yaml._to_decimal("oops") is None  # noqa: SLF001
    assert oc_yaml._to_decimal("NaN") is None  # noqa: SLF001


def test_compile_call_by_post_field_covers_ctx_kinds_and_ensure_field_value_branches() -> None:
    spec = oc_yaml._compile_call_by_post_field(  # noqa: SLF001
        out_field_id="v",
        call_by="tests.call_by_fns:needs_ctx_attr($ctx.row_id)",
        resolver=_tests_resolver(),
    )
    assert spec.calculator({}) is None

    spec = oc_yaml._compile_call_by_post_field(  # noqa: SLF001
        out_field_id="v",
        call_by="tests.call_by_fns:echo($ctx)",
        resolver=_tests_resolver(),
    )
    with pytest.raises(TypeError, match=r"unsupported value type"):
        _ = spec.calculator({})


def test_eval_call_by_value_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match=r"Unknown call_by value kind"):
        _ = oc_yaml._eval_call_by_value(  # noqa: SLF001
            field_id="v",
            value=CallByValue(kind="bad", value=None),
            row={},
            ctx=oc_yaml._AggregateCallByContext(row_id=None, batch_num=0, field_id="v", deps=(), values={}),  # noqa: SLF001
        )


def test_compile_call_by_post_field_rejects_parse_and_resolve_errors() -> None:
    with pytest.raises(ValueError, match=r"invalid call_by"):
        _ = oc_yaml._compile_call_by_post_field(out_field_id="v", call_by="bad", resolver=_tests_resolver())  # noqa: SLF001

    with pytest.raises(ValueError, match=r"failed to resolve call_by reference"):
        _ = oc_yaml._compile_call_by_post_field(  # noqa: SLF001
            out_field_id="v",
            call_by="tests.call_by_fns:echo(1)",
            resolver=_resolver(),
        )


def test_score_by_rank_post_field_handles_missing_rank_and_invalid_rank_types() -> None:
    spec = oc_yaml._compile_score_by_rank_post_field(out_field_id="score", cfg={})  # noqa: SLF001
    assert spec.calculator({}) is None

    with pytest.raises(TypeError, match=r"requires integer rank"):
        _ = spec.calculator({"rank": "oops"})


def test_compile_compute_post_field_executes_expression_and_validates_result_type() -> None:
    engine = SecureComputeEngine()

    spec = oc_yaml._compile_compute_post_field(  # noqa: SLF001
        out_field_id="v",
        cfg={"expression": "a + b", "dependencies": ("a", "b")},
        engine=engine,
    )
    assert spec.dependencies == ("a", "b")
    assert spec.calculator({"a": Decimal("1.5"), "b": 2}) == Decimal("3.5")

    bad_type = oc_yaml._compile_compute_post_field(  # noqa: SLF001
        out_field_id="v",
        cfg={"expression": "[]", "dependencies": ()},
        engine=engine,
    )
    with pytest.raises(TypeError, match=r"unsupported value type"):
        _ = bad_type.calculator({})

    with pytest.raises(ValueError, match=r"invalid compute expression"):
        _ = oc_yaml._compile_compute_post_field(  # noqa: SLF001
            out_field_id="v",
            cfg={"expression": "a +", "dependencies": ("a",)},
            engine=engine,
        )

    with pytest.raises(ValueError, match=r"missing expression"):
        _ = oc_yaml._compile_compute_post_field(  # noqa: SLF001
            out_field_id="v",
            cfg={"expression": "   ", "dependencies": ()},
            engine=engine,
        )
