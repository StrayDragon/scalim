from decimal import Decimal
from pathlib import Path

import pytest

from scalim.dsl.by_yaml.config_parsing.call_by import CallByValue
from scalim.dsl.by_yaml.config_parsing.security import SecureComputeEngine
from scalim.dsl.by_yaml.init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError
from scalim.dsl.by_yaml.runtime import output_composition_yaml as oc_yaml
from scalim.dsl.by_yaml.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.by_yaml.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    OutputAggregateConfig,
    OutputAggregateFieldConfig,
    OutputContainerConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    ResourcesConfig,
)
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import MainSourceIr


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
    return SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"]))


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
            default_workbook_path=None,
            default_allow_formulas=False,
            default_write_lock=False,
            as_in_memory_csv=False,
        )


def test_compile_output_composition_meta_audit_requires_outputs() -> None:
    config = DemandConfig(meta=OutputExtraSheetConfig())

    with pytest.raises(ValueError, match=r"meta/audit requires outputs"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_returns_none_when_no_outputs() -> None:
    assert oc_yaml.compile_output_composition_from_yaml(DemandConfig(), _make_demand_ir(), resolver=_resolver()) is None


def test_compile_output_composition_can_skip_extra_sheet_without_workbook() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path="./out.csv"),
                fields=("a",),
            ),
        ),
        meta=OutputExtraSheetConfig(),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        resolver=_resolver(),
        skip_extra_sheets_without_workbook=True,
    )
    assert spec is not None
    assert spec.meta_sheet is None


def test_compile_output_composition_skip_flag_keeps_explicit_extra_sheet_path() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path="./out.csv"),
                fields=("a",),
            ),
        ),
        meta=OutputExtraSheetConfig(path="./meta.xlsx"),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        resolver=_resolver(),
        skip_extra_sheets_without_workbook=True,
    )
    assert spec is not None
    assert spec.meta_sheet is not None
    assert spec.meta_sheet.output.path == "./meta.xlsx"


def test_compile_output_composition_resolves_output_container_path_init_var() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": "output_path"}),
                fields=("a",),
            ),
        )
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        resolver=_resolver(),
        init_vars={"output_path": "./out.csv"},
    )
    assert spec is not None
    assert spec.targets[0].output.path == "./out.csv"


def test_compile_output_composition_requires_output_container_path_init_var_value() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": "output_path"}),
                fields=("a",),
            ),
        )
    )

    with pytest.raises(ValueError, match=r"outputs\.0\.container\.path"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_rejects_output_container_path_init_var_shape_errors() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": "out_path", "other": 1}),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ScalimInitVarNodeValueError) as excinfo:
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": "./out.csv"}
        )
    assert excinfo.value.path == "outputs.0.container.path"
    assert excinfo.value.reason == "only supports {$init_var: <name>}; unexpected keys: other"

    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={}),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ScalimInitVarNodeValueError) as excinfo:
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": "./out.csv"}
        )
    assert excinfo.value.path == "outputs.0.container.path"
    assert excinfo.value.reason == "only supports {$init_var: <name>}; missing '$init_var'"

    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": None}),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ScalimInitVarNodeTypeError) as excinfo:
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": "./out.csv"}
        )
    assert excinfo.value.path == "outputs.0.container.path.$init_var"
    assert excinfo.value.reason == "must be a non-empty string"

    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": " "}),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ScalimInitVarNodeTypeError) as excinfo:
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": "./out.csv"}
        )
    assert excinfo.value.path == "outputs.0.container.path.$init_var"
    assert excinfo.value.reason == "must be a non-empty string"


def test_compile_output_composition_validates_init_var_value_types_and_normalizes_path() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path={"$init_var": "out_path"}),
                fields=("a",),
            ),
        )
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        resolver=_resolver(),
        init_vars={"out_path": " ./out.csv "},
    )
    assert spec is not None
    assert spec.targets[0].output.path == "./out.csv"

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        resolver=_resolver(),
        init_vars={"out_path": Path("output/out.csv")},
    )
    assert spec is not None
    assert spec.targets[0].output.path == "output/out.csv"

    with pytest.raises(ValueError, match=r"resolved to None"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": None})

    with pytest.raises(TypeError, match=r"must be str or os\.PathLike"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": 1})

    with pytest.raises(ValueError, match=r"resolved to an empty string"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver(), init_vars={"out_path": "   "})


def test_compile_output_composition_rejects_empty_or_missing_container_path_values() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path=None),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ValueError, match=r"is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())

    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=OutputContainerConfig(type="csv", path="   "),
                fields=("a",),
            ),
        )
    )
    with pytest.raises(ValueError, match=r"is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_meta_output_name_is_reserved() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(
                name="meta",
                container=OutputContainerConfig(type="csv", path="./out.csv"),
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
                container=OutputContainerConfig(type="csv", path="./out.csv"),
                fields=("a",),
            ),
        ),
        audit=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'audit'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_compile_output_composition_requires_to_book_binding_when_container_missing() -> None:
    config = DemandConfig(outputs=(OutputTargetConfig(name="detail", container=None, fields=("a",)),))

    with pytest.raises(ValueError, match=r"Missing outputs to\.book binding"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())


def test_validate_excel_sheet_name_errors_cover_empty_too_long_and_invalid_chars() -> None:
    with pytest.raises(ValueError, match=r"Excel sheet name must be non-empty"):
        oc_yaml._validate_excel_sheet_name("", path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"Excel sheet name is too long"):
        oc_yaml._validate_excel_sheet_name("x" * 32, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"invalid characters"):
        oc_yaml._validate_excel_sheet_name("A/B", path="p")  # noqa: SLF001


def test_compile_extra_sheet_workflow_managed_mode_rejects_path() -> None:
    with pytest.raises(ValueError, match=r"workflow-managed mode"):
        _ = oc_yaml._compile_extra_sheet(  # noqa: SLF001
            target_id="meta",
            cfg=OutputExtraSheetConfig(path="./meta.xlsx"),
            default_sheet="__meta__",
            default_workbook_path=None,
            default_allow_formulas=False,
            default_write_lock=False,
            as_in_memory_csv=True,
        )


def test_require_book_resource_and_resolve_book_export_path_errors_cover_branches() -> None:
    config = DemandConfig()

    with pytest.raises(ValueError, match=r"Missing book resource id"):
        _ = oc_yaml._require_book_resource(config, book_id="missing", book_ref_path="outputs.0.to.book")  # noqa: SLF001

    config = DemandConfig(resources=ResourcesConfig(books={"mem": BookConfig(kind="xlsx_memory")}))
    with pytest.raises(ValueError, match=r"requires export_xlsx"):
        _ = oc_yaml._resolve_book_export_path(  # noqa: SLF001
            config,
            book_id="mem",
            book_ref_path="outputs_defaults.to.book",
            yaml_base_dir=".",
            init_vars=None,
        )

    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "mem": BookConfig(
                    kind="xlsx_memory",
                    budget=BookBudgetConfig(max_sheets=1, max_total_cells=1),
                    export_xlsx=BookExportXlsxConfig(path="./export.xlsx", write_lock=True, allow_formulas=True),
                )
            }
        )
    )
    export_path, allow_formulas, write_lock = oc_yaml._resolve_book_export_path(  # noqa: SLF001
        config,
        book_id="mem",
        book_ref_path="outputs_defaults.to.book",
        yaml_base_dir=".",
        init_vars=None,
    )
    assert export_path.endswith("export.xlsx")
    assert allow_formulas is True
    assert write_lock is True

    config = DemandConfig(resources=ResourcesConfig(books={"bad": BookConfig(kind="nope")}))
    with pytest.raises(ValueError, match=r"Unknown book kind"):
        _ = oc_yaml._resolve_book_export_path(  # noqa: SLF001
            config,
            book_id="bad",
            book_ref_path="outputs_defaults.to.book",
            yaml_base_dir=".",
            init_vars=None,
        )


def test_compile_output_composition_book_sheet_default_name_error_and_yaml_base_dir_required() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}),
        outputs=(
            OutputTargetConfig(
                name="Bad/Name",
                container=None,
                to=OutputToConfig(book="report"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"Invalid default Excel sheet name"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver(), yaml_base_dir=".")

    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=None,
                to=OutputToConfig(book="report", sheet="S"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"yaml_base_dir is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver())

    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="./out.xlsx")}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                container=None,
                to=OutputToConfig(book="report", sheet="A/B"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"outputs\.0\.to\.sheet"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), resolver=_resolver(), yaml_base_dir=".")


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
        call_by="tests.fixtures.call_by_fns:needs_ctx_attr($ctx.row_id)",
        resolver=_tests_resolver(),
    )
    assert spec.calculator({}) is None

    spec = oc_yaml._compile_call_by_post_field(  # noqa: SLF001
        out_field_id="v",
        call_by="tests.fixtures.call_by_fns:echo($ctx)",
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
            call_by="tests.fixtures.call_by_fns:echo(1)",
            resolver=_resolver(),
        )


def test_compile_call_by_post_field_rejects_non_callable_reference() -> None:
    with pytest.raises(ValueError, match=r"failed to resolve call_by reference"):
        _ = oc_yaml._compile_call_by_post_field(  # noqa: SLF001
            out_field_id="v",
            call_by="tests.fixtures.call_by_fns:NOT_CALLABLE()",
            resolver=_tests_resolver(),
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
