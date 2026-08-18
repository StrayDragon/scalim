from decimal import Decimal
from pathlib import Path

import pytest

from scalim.dsl.yaml_dsl._internal.config_parsing.call_by import CallByValue
from scalim.dsl.yaml_dsl._internal.config_parsing.security import SecureComputeEngine
from scalim.dsl.yaml_dsl.init_var_nodes import InitVarRef
from scalim.dsl.yaml_dsl.runtime import output_composition_yaml as oc_yaml
from scalim.dsl.yaml_dsl.runtime.references import SecurePythonReferenceResolver
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    OutputAggregateConfig,
    OutputAggregateFieldConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)
from scalim.spec.ir import DemandIr
from scalim.spec.ir import FieldIr
from scalim.spec.ir import MainSourceIr
from scalim.spec.ir.callable_refs import RuntimeHandleIdIr


def _dummy_main_loader(*_args, **_kwargs):  # type: ignore[no-untyped-def]
    return []


def _make_demand_ir(*, field_name_by_id=None) -> DemandIr:  # type: ignore[no-untyped-def]
    main = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
    field_irs = []
    if field_name_by_id:
        for field_id, name in field_name_by_id.items():
            field_irs.append(FieldIr(field_id=field_id, name=name, source_id=main.source_id))
    return DemandIr.from_irs(sources=[], fields=field_irs, main_source=main, name="demo")


def _resolver() -> SecurePythonReferenceResolver:
    return SecurePythonReferenceResolver(allowed_modules=frozenset(["scalim"]))


def _tests_resolver() -> SecurePythonReferenceResolver:
    return SecurePythonReferenceResolver(allowed_modules=frozenset(["tests.fixtures.call_by_fns"]))


def _csv_config(path):  # type: ignore[no-untyped-def]
    return DemandConfig(
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path=path)}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(file="detail_csv"),
                fields=("a",),
            ),
        ),
    )


def test_compile_call_by_post_field_fast_fails_on_kwonly_signature_mismatch() -> None:
    resolver = _tests_resolver()
    with pytest.raises(ValueError, match="函数签名不匹配"):
        oc_yaml._compile_call_by_post_field(  # noqa: SLF001
            out_field_id="ok",
            call_by="tests.fixtures.call_by_fns:is_valid_group(group_name)",
            resolver=resolver,
        )


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
            as_in_memory_csv=False,
        )


def test_compile_output_composition_meta_audit_requires_outputs() -> None:
    config = DemandConfig(meta=OutputExtraSheetConfig())

    with pytest.raises(ValueError, match=r"meta/audit requires outputs"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())


def test_compile_output_composition_returns_none_when_no_outputs() -> None:
    assert oc_yaml.compile_output_composition_from_yaml(DemandConfig(), _make_demand_ir(), version_id="run_0", resolver=_resolver()) is None


def test_compile_output_composition_keeps_xlsx_memory_internal_headers_canonical() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "mem": BookConfig(
                    export_xlsx=BookExportXlsxConfig(path="./out"),
                )
            }
        ),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="mem", sheet="S"),
                write=OutputWriteConfig(header_fields_output_by="name"),
                fields=("order_id", "amount"),
            ),
        ),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(field_name_by_id={"order_id": "Order ID", "amount": "Amount"}),
        version_id="run_0",
        resolver=_resolver(),
        workflow_managed_output_ids=frozenset(["detail"]),
    )

    assert spec is not None
    target = spec.targets[0]
    assert target.layout.field_ids == ("order_id", "amount")
    assert target.layout.header_names is None
    assert target.workflow_export_header == ("Order ID", "Amount")
    assert target.managed_artifact_kind == "rows"


def test_compile_output_composition_xlsx_file_managed_uses_rows_and_excel_format(tmp_path: Path) -> None:
    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path=str(tmp_path / "out"))}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("order_id", "amount"),
            ),
        ),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(field_name_by_id={"order_id": "Order ID", "amount": "Amount"}),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=str(tmp_path),
        workflow_managed_output_ids=frozenset(["detail"]),
    )

    assert spec is not None
    target = spec.targets[0]
    assert target.managed_artifact_kind == "rows"
    assert target.output.format == "excel"


def test_compile_output_composition_accepts_pathful_book_regardless_of_legacy_kind_shim(tmp_path: Path) -> None:
    """c25: 身份由 path 决定;legacy kind 字面量不再拦截 managed rows."""

    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(kind="future_book", path=str(tmp_path / "out"))}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("order_id",),
            ),
        ),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(field_name_by_id={"order_id": "Order ID"}),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=str(tmp_path),
        workflow_managed_output_ids=frozenset(["detail"]),
    )
    assert spec is not None
    assert spec.targets[0].managed_artifact_kind == "rows"


def test_compile_output_composition_can_skip_extra_sheet_without_workbook() -> None:
    config = _csv_config("./out")
    config = DemandConfig(resources=config.resources, outputs=config.outputs, meta=OutputExtraSheetConfig())

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=".",
        skip_extra_sheets_without_workbook=True,
    )
    assert spec is not None
    assert spec.meta_sheet is None


def test_compile_output_composition_skip_flag_keeps_explicit_extra_sheet_path() -> None:
    config = _csv_config("./out")
    config = DemandConfig(resources=config.resources, outputs=config.outputs, meta=OutputExtraSheetConfig(path="./meta.xlsx"))

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=".",
        skip_extra_sheets_without_workbook=True,
    )
    assert spec is not None
    assert spec.meta_sheet is not None
    assert spec.meta_sheet.output.path == "./meta.xlsx"


def test_compile_output_composition_resolves_file_resource_path_init_var() -> None:
    config = _csv_config(InitVarRef(name="output_path", path="resources.files.detail_csv.csv_file.path"))

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        version_id="run_0",
        resolver=_resolver(),
        init_vars={"output_path": "./out"},
        yaml_base_dir=".",
    )
    assert spec is not None
    assert spec.targets[0].output.path == str((Path(".") / "out" / "versions" / "run_0" / "files" / "detail_csv.csv").resolve(strict=False))


def test_compile_output_composition_requires_file_resource_path_init_var_value() -> None:
    config = _csv_config(InitVarRef(name="output_path", path="resources.files.detail_csv.csv_file.path"))

    with pytest.raises(ValueError, match=r"resources\.files\.detail_csv\.csv_file\.path"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )


def test_compile_output_composition_validates_init_var_value_types_and_normalizes_path() -> None:
    config = _csv_config(InitVarRef(name="out_path", path="resources.files.detail_csv.csv_file.path"))

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        version_id="run_0",
        resolver=_resolver(),
        init_vars={"out_path": " ./out "},
        yaml_base_dir=".",
    )
    assert spec is not None
    assert spec.targets[0].output.path == str((Path(".") / "out" / "versions" / "run_0" / "files" / "detail_csv.csv").resolve(strict=False))

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(),
        version_id="run_0",
        resolver=_resolver(),
        init_vars={"out_path": Path("output")},
        yaml_base_dir=".",
    )
    assert spec is not None
    assert spec.targets[0].output.path == str(
        (Path(".") / "output" / "versions" / "run_0" / "files" / "detail_csv.csv").resolve(strict=False)
    )

    with pytest.raises(ValueError, match=r"resolved to None"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), init_vars={"out_path": None}, yaml_base_dir="."
        )

    with pytest.raises(TypeError, match=r"must be str or os\.PathLike"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), init_vars={"out_path": 1}, yaml_base_dir="."
        )

    with pytest.raises(ValueError, match=r"resolved to an empty string"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), init_vars={"out_path": "   "}, yaml_base_dir="."
        )


def test_compile_output_composition_requires_yaml_base_dir_for_file_outputs() -> None:
    config = _csv_config("./out")
    with pytest.raises(ValueError, match=r"yaml_base_dir is required to resolve resources\.files output paths"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())


def test_compile_output_composition_missing_file_resource_raises_helpful_error() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(files={}),
        outputs=(OutputTargetConfig(name="detail", to=OutputToConfig(file="missing_csv"), fields=("a",)),),
    )
    with pytest.raises(ValueError, match=r"Missing file resource id 'missing_csv'"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )


def test_compile_output_composition_append_mode_rejects_include_header() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path="./out", write_defaults=BookWriteDefaultsConfig(mode="append"))}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="Detail"),
                write=OutputWriteConfig(include_header=True),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"outputs\.0\.write\.include_header is not allowed for append-mode book outputs"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )


def test_compile_output_composition_append_mode_uses_header_policy_when_include_header_omitted() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    path="./out",
                    write_defaults=BookWriteDefaultsConfig(mode="append", header_policy="once"),
                )
            }
        ),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="Detail"),
                fields=("a",),
            ),
        ),
    )
    composition = oc_yaml.compile_output_composition_from_yaml(
        config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
    )
    assert composition is not None


def test_compile_output_composition_rejects_empty_or_missing_file_resource_path_values() -> None:
    config = _csv_config(None)
    with pytest.raises(ValueError, match=r"is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )

    config = _csv_config("   ")
    with pytest.raises(ValueError, match=r"is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )


def test_compile_output_composition_meta_output_name_is_reserved() -> None:
    base = _csv_config("./out")
    config = DemandConfig(
        resources=base.resources,
        outputs=(OutputTargetConfig(name="meta", to=OutputToConfig(file="detail_csv"), fields=("a",)),),
        meta=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'meta'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())


def test_compile_output_composition_audit_output_name_is_reserved() -> None:
    base = _csv_config("./out")
    config = DemandConfig(
        resources=base.resources,
        outputs=(OutputTargetConfig(name="audit", to=OutputToConfig(file="detail_csv"), fields=("a",)),),
        audit=OutputExtraSheetConfig(),
    )

    with pytest.raises(ValueError, match=r"cannot be 'audit'"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())


def test_compile_output_composition_requires_output_destination_binding() -> None:
    config = DemandConfig(outputs=(OutputTargetConfig(name="detail", fields=("a",)),))

    with pytest.raises(ValueError, match=r"Missing output destination"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())


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
            as_in_memory_csv=True,
        )


def test_require_book_resource_and_resolve_book_export_path_errors_cover_branches() -> None:
    config = DemandConfig()

    with pytest.raises(ValueError, match=r"Missing book resource id"):
        _ = oc_yaml._require_book_resource(config, book_id="missing", book_ref_path="outputs.0.to.book")  # noqa: SLF001

    config = DemandConfig(resources=ResourcesConfig(books={"mem": BookConfig()}))
    with pytest.raises(ValueError, match=r"requires export_xlsx"):
        _ = oc_yaml._resolve_book_export_path(  # noqa: SLF001
            config,
            book_id="mem",
            book_ref_path="outputs.0.to.book",
            yaml_base_dir=".",
            init_vars=None,
            version_id="run_0",
        )

    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "mem": BookConfig(
                    export_xlsx=BookExportXlsxConfig(path="./out", allow_formulas=True),
                )
            }
        )
    )
    export_path, allow_formulas = oc_yaml._resolve_book_export_path(  # noqa: SLF001
        config,
        book_id="mem",
        book_ref_path="outputs.0.to.book",
        yaml_base_dir=".",
        init_vars=None,
        version_id="run_0",
    )
    assert export_path.endswith(str(Path("books") / "mem.xlsx"))
    assert allow_formulas is True

    config = DemandConfig(resources=ResourcesConfig(books={"bad": BookConfig(kind="nope")}))
    with pytest.raises(ValueError, match=r"pathless book requires export_xlsx"):
        _ = oc_yaml._resolve_book_export_path(  # noqa: SLF001
            config,
            book_id="bad",
            book_ref_path="outputs.0.to.book",
            yaml_base_dir=".",
            init_vars=None,
            version_id="run_0",
        )


def test_compile_output_composition_book_sheet_default_name_error_and_yaml_base_dir_required() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path="./out")}),
        outputs=(
            OutputTargetConfig(
                name="Bad/Name",
                to=OutputToConfig(book="report"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"Invalid default Excel sheet name"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )

    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path="./out")}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="S"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"yaml_base_dir is required"):
        _ = oc_yaml.compile_output_composition_from_yaml(config, _make_demand_ir(), version_id="run_0", resolver=_resolver())

    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path="./out")}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="A/B"),
                fields=("a",),
            ),
        ),
    )
    with pytest.raises(ValueError, match=r"outputs\.0\.to\.sheet"):
        _ = oc_yaml.compile_output_composition_from_yaml(
            config, _make_demand_ir(), version_id="run_0", resolver=_resolver(), yaml_base_dir="."
        )


def test_compile_output_composition_books_default_header_uses_field_name() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(books={"report": BookConfig(path="./out")}),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="明细"),
                fields=("order_id", "user_name"),
            ),
        ),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(field_name_by_id={"order_id": "订单ID", "user_name": "用户姓名"}),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=".",
    )
    assert spec is not None
    assert spec.targets[0].layout.header_names == ("订单ID", "用户姓名")


def test_compile_output_composition_books_write_override_changes_header_source() -> None:
    config = DemandConfig(
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    path="./out",
                )
            }
        ),
        outputs=(
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="明细"),
                write=OutputWriteConfig(header_fields_output_by="field_id"),
                fields=("order_id", "user_name"),
            ),
        ),
    )

    spec = oc_yaml.compile_output_composition_from_yaml(
        config,
        _make_demand_ir(field_name_by_id={"order_id": "订单ID", "user_name": "用户姓名"}),
        version_id="run_0",
        resolver=_resolver(),
        yaml_base_dir=".",
    )
    assert spec is not None
    assert spec.targets[0].layout.header_names is None


def test_validate_xlsx_memory_write_contract_reports_book_default_align_by_path() -> None:
    book = BookConfig(
        write_defaults=BookWriteDefaultsConfig(mode="append", align_by="header"),
    )

    with pytest.raises(ValueError, match=r"resources\.books\.report\.write_defaults\.align_by"):
        oc_yaml._validate_xlsx_memory_write_contract(  # noqa: SLF001
            book=book,
            book_id="report",
        )


def test_validate_xlsx_memory_write_contract_accepts_field_id_alignment() -> None:
    book = BookConfig(
        write_defaults=BookWriteDefaultsConfig(mode="append", align_by="field_id"),
    )

    oc_yaml._validate_xlsx_memory_write_contract(  # noqa: SLF001
        book=book,
        book_id="report",
    )


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


def test_get_derived_field_name_falls_back_when_agg_name_is_blank() -> None:
    demand_ir = _make_demand_ir()
    agg = OutputAggregateConfig(
        group_by=(),
        fields={
            "m": OutputAggregateFieldConfig(
                producer_key="count",
                config={},
                name=" ",
            )
        },
    )

    assert oc_yaml._get_derived_field_name("m", demand_ir, agg) == "m"  # noqa: SLF001
    assert oc_yaml._get_derived_field_name("missing", demand_ir, agg) == "missing"  # noqa: SLF001


def test_effective_file_and_book_ids_return_none_for_blank_refs() -> None:
    out_cfg = OutputTargetConfig(
        name="detail",
        to=OutputToConfig(file=" "),
        fields=("a",),
    )
    file_id, file_path = oc_yaml._effective_file_id_for_output(out_cfg, idx=0, outputs_path="outputs")  # noqa: SLF001
    assert file_id is None
    assert file_path == "outputs.0.to.file"

    out_cfg = OutputTargetConfig(
        name="detail",
        to=OutputToConfig(book=" "),
        fields=("a",),
    )
    book_id, book_path = oc_yaml._effective_book_id_for_output(out_cfg, idx=1, outputs_path="outputs")  # noqa: SLF001
    assert book_id is None
    assert book_path == "outputs.1.to.book"


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


def test_validate_output_root_path_rejects_file_path_suffixes() -> None:
    with pytest.raises(ValueError, match=r"expects an output root directory"):
        oc_yaml._validate_output_root_path("out.xlsx", path="resources.books.report.xlsx_file.path")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"expects an output root directory"):
        oc_yaml._validate_output_root_path("out.csv", path="resources.files.detail_csv.csv_file.path")  # noqa: SLF001


def test_try_resolve_workflow_managed_book_export_path_returns_none_for_unknown_kind() -> None:
    book = BookConfig(kind="unknown")
    assert (
        oc_yaml._try_resolve_workflow_managed_book_export_path(  # noqa: SLF001
            book,
            book_id="book",
            yaml_base_dir=".",
            init_vars={},
            version_id="run_0",
        )
        is None
    )


def test_try_resolve_workflow_managed_book_export_path_xlsx_memory_with_export(tmp_path: Path) -> None:
    book = BookConfig(export_xlsx=BookExportXlsxConfig(path=str(tmp_path / "out")))
    path = oc_yaml._try_resolve_workflow_managed_book_export_path(  # noqa: SLF001
        book,
        book_id="mem",
        yaml_base_dir=str(tmp_path),
        init_vars={},
        version_id="run_0",
    )
    assert path is not None
    assert str(path).endswith(".xlsx")
