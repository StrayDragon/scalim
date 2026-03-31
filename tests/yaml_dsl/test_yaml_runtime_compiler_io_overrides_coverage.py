import os

import pytest

from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
from scalim.dsl.by_yaml.runtime.contracts import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    FileResourceOverride,
    OutputDefaultsToOverride,
    OutputsDefaultsOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOptions,
    RunOverrides,
)
from scalim.dsl.by_yaml.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    FileConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
    ResourcesConfig,
)


class _BlankPathLike(os.PathLike):
    def __init__(self, value: str) -> None:
        self._value = str(value)

    def __fspath__(self) -> str:
        return self._value


def test_runtime_compiler_parse_outputs_defaults_book_id_cover_branches() -> None:
    assert compiler_mod._parse_overrides_outputs_defaults_book_id(None, path="p") is None  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p must be an OutputsDefaultsOverride"):
        _ = compiler_mod._parse_overrides_outputs_defaults_book_id(object(), path="p")  # type: ignore[arg-type]  # noqa: SLF001

    with pytest.raises(TypeError, match=r"OutputsDefaultsOverride\.to must be an OutputDefaultsToOverride"):
        _ = OutputsDefaultsOverride(to=object())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match=r"p\.to\.book is required"):
        _ = compiler_mod._parse_overrides_outputs_defaults_book_id(  # noqa: SLF001
            OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="   ")),
            path="p",
        )

    assert (
        compiler_mod._parse_overrides_outputs_defaults_book_id(  # noqa: SLF001
            OutputsDefaultsOverride(to=OutputDefaultsToOverride(book=" report ")),
            path="p",
        )
        == "report"
    )

    with pytest.raises(TypeError, match=r"RunOverrides\.outputs_defaults must be an OutputsDefaultsOverride"):
        _ = RunOverrides(outputs_defaults=object())  # type: ignore[arg-type]


def test_runtime_compiler_parse_typed_overrides_output_to_cover_branches() -> None:
    raw = OutputToOverride(file="f", book="b", sheet="s")
    object.__setattr__(raw, "file", "")
    object.__setattr__(raw, "book", "")
    object.__setattr__(raw, "sheet", "")

    parsed = compiler_mod._parse_typed_overrides_output_to(raw)  # noqa: SLF001
    assert parsed.file is None
    assert parsed.book is None
    assert parsed.sheet is None


def test_runtime_compiler_apply_default_book_binding_to_outputs_cover_branches() -> None:
    outputs = (
        OutputTargetConfig(name="detail", to=None, fields=("order_id",)),
        OutputTargetConfig(name="csv", to=OutputToConfig(file="detail_csv"), fields=("order_id",)),
        OutputTargetConfig(name="sheet_only", to=OutputToConfig(sheet="S"), fields=("order_id",)),
    )
    bound = compiler_mod._apply_default_book_binding_to_outputs(outputs, default_book_id="report")  # noqa: SLF001
    assert bound[0].to is not None
    assert bound[0].to.book == "report"
    assert bound[1].to is not None
    assert bound[1].to.file == "detail_csv"
    assert bound[2].to is not None
    assert bound[2].to.book == "report"
    assert bound[2].to.sheet == "S"


def test_runtime_compiler_apply_default_book_binding_to_outputs_returns_input_when_disabled() -> None:
    assert compiler_mod._apply_default_book_binding_to_outputs((), default_book_id="report") == ()  # noqa: SLF001

    outputs = (OutputTargetConfig(name="detail", to=None, fields=("order_id",)),)
    assert compiler_mod._apply_default_book_binding_to_outputs(outputs, default_book_id="") is outputs  # noqa: SLF001


def test_runtime_compiler_resolve_effective_outputs_and_path_apply_defaults_cover_branches() -> None:
    config = DemandConfig(
        outputs=(
            OutputTargetConfig(name="detail", to=None, fields=("order_id",)),
            OutputTargetConfig(name="sheet_only", to=OutputToConfig(sheet="S"), fields=("order_id",)),
        )
    )
    options = RunOptions(
        allowed_modules=frozenset(["tests.fixtures"]),
        overrides=RunOverrides(outputs_defaults=OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="report"))),
    )
    outputs, outputs_ref = compiler_mod._resolve_effective_outputs_and_path(config, object(), options=options)  # type: ignore[arg-type]  # noqa: SLF001
    assert outputs_ref == "outputs"
    assert outputs[0].to is not None
    assert outputs[0].to.book == "report"
    assert outputs[1].to is not None
    assert outputs[1].to.book == "report"
    assert outputs[1].to.sheet == "S"


def test_runtime_compiler_parse_overrides_outputs_targets_cover_error_branches() -> None:
    class _FakeDemandIr:
        fields = ("order_id",)

    demand_ir = _FakeDemandIr()

    with pytest.raises(TypeError, match=r"p must be a sequence of OutputOverride"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # type: ignore[arg-type]  # noqa: SLF001
            object(),
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    with pytest.raises(ValueError, match=r"p cannot be empty"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    with pytest.raises(TypeError, match=r"p\.0 must be an OutputOverride"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # type: ignore[list-item]  # noqa: SLF001
            [object()],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_cfg = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"))
    object.__setattr__(out_cfg, "fields", ["order_id"])
    with pytest.raises(TypeError, match=r"p\.0\.fields must be a tuple\[str, \.\.\.\]"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_cfg],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_bad_field_type = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"))
    object.__setattr__(out_bad_field_type, "fields", (1,))  # type: ignore[assignment]
    with pytest.raises(TypeError, match=r"p\.0\.fields\.0 must be a field_id string"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_field_type],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_empty_field = OutputOverride(name="detail", fields=("   ",), to=OutputToOverride(file="detail_csv"))
    with pytest.raises(ValueError, match=r"p\.0\.fields\.0 must not be empty"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_empty_field],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_bad_to = OutputOverride(name="detail", fields=("order_id",), to=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"p\.0\.to must be an OutputToOverride"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_to],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_bad_write = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"), write=object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"p\.0\.write must be an OutputWriteOverride"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_write],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )

    out_file_with_book_only_keys = OutputOverride(
        name="detail",
        fields=("order_id",),
        to=OutputToOverride(file="detail_csv"),
        write=OutputWriteOverride(
            mode="append",
            align_by="name",
            header_policy="always",
            on_mismatch="error",
            on_conflict="error",
        ),
    )
    with pytest.raises(ValueError, match=r"only apply to book outputs"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_file_with_book_only_keys],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )


def test_runtime_compiler_output_requires_unique_effective_field_display_names_cover_branches() -> None:
    out_cfg = OutputTargetConfig(
        name="detail",
        to=OutputToConfig(book="  "),
        write=OutputWriteConfig(header_fields_output_by="name"),
        fields=("order_id",),
    )
    assert compiler_mod._output_requires_unique_effective_field_display_names(DemandConfig(), out_cfg) is False  # noqa: SLF001


def test_runtime_compiler_overlay_book_write_defaults_override_invalid_enum_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"Invalid write_defaults\.mode"):
        _ = compiler_mod._overlay_book_write_defaults_override(  # noqa: SLF001
            None,
            BookWriteDefaultsOverride(mode="nope"),
            path="p",
        )


def test_runtime_compiler_overlay_book_budget_override_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"requires max_sheets and max_total_cells"):
        _ = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
            None,
            BookBudgetOverride(max_sheets=None, max_total_cells=2),
            path="p",
        )

    base_budget = BookBudgetConfig(max_sheets=1, max_total_cells=2)
    merged = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
        base_budget,
        BookBudgetOverride(max_sheets=None, max_total_cells=3),
        path="p",
    )
    assert merged.max_sheets == 1
    assert merged.max_total_cells == 3

    with pytest.raises(TypeError, match=r"p\.max_sheets must be an integer"):
        _ = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
            None,
            BookBudgetOverride(max_sheets=True, max_total_cells=2),  # type: ignore[arg-type]
            path="p",
        )

    with pytest.raises(TypeError, match=r"p\.max_total_cells must be an integer"):
        _ = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
            None,
            BookBudgetOverride(max_sheets=1, max_total_cells=True),  # type: ignore[arg-type]
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.max_sheets must be >= 1"):
        _ = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
            None,
            BookBudgetOverride(max_sheets=0, max_total_cells=2),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.max_total_cells must be >= 1"):
        _ = compiler_mod._overlay_book_budget_override(  # noqa: SLF001
            None,
            BookBudgetOverride(max_sheets=1, max_total_cells=0),
            path="p",
        )


def test_runtime_compiler_overlay_book_export_xlsx_override_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p\.path is required when creating export_xlsx"):
        _ = compiler_mod._overlay_book_export_xlsx_override(None, BookExportXlsxOverride(path=None), path="p")  # noqa: SLF001

    base = BookExportXlsxConfig(path="a.xlsx", write_lock=False, allow_formulas=False)
    updated = compiler_mod._overlay_book_export_xlsx_override(  # noqa: SLF001
        base,
        BookExportXlsxOverride(path="b.xlsx", write_lock=True, allow_formulas=True),
        path="p",
    )
    assert updated.path == "b.xlsx"
    assert updated.write_lock is True
    assert updated.allow_formulas is True


def test_runtime_compiler_apply_book_override_semantic_and_type_errors_cover_branches() -> None:
    base_file = BookConfig(kind="xlsx_file", path="a.xlsx")
    with pytest.raises(TypeError, match=r"p\.allow_formulas must be a bool"):
        _ = compiler_mod._apply_book_override(base_file, BookResourceOverride(allow_formulas="yes"), path="p")  # type: ignore[arg-type]  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.write_lock must be a bool"):
        _ = compiler_mod._apply_book_override(base_file, BookResourceOverride(write_lock="yes"), path="p")  # type: ignore[arg-type]  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget is not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a.xlsx", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1)),
            BookResourceOverride(),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.export_xlsx is not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            BookConfig(
                kind="xlsx_file",
                path="a.xlsx",
                export_xlsx=BookExportXlsxConfig(path="x.xlsx", write_lock=False, allow_formulas=False),
            ),
            BookResourceOverride(),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.path is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            BookConfig(kind="xlsx_memory", path="a.xlsx", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1)),
            BookResourceOverride(),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.allow_formulas is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            BookConfig(
                kind="xlsx_memory",
                budget=BookBudgetConfig(max_sheets=1, max_total_cells=1),
                allow_formulas=True,
            ),
            BookResourceOverride(),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.write_lock is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            BookConfig(
                kind="xlsx_memory",
                budget=BookBudgetConfig(max_sheets=1, max_total_cells=1),
                write_lock=True,
            ),
            BookResourceOverride(),
            path="p",
        )


def test_runtime_compiler_apply_file_override_non_empty_kind_validation_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p\.kind must be a non-empty string"):
        _ = compiler_mod._apply_file_override(  # noqa: SLF001
            FileConfig(kind="csv_file", path="a.csv"),
            FileResourceOverride(kind="  "),
            path="p",
        )


def test_runtime_compiler_apply_resources_override_type_checks_cover_branches() -> None:
    with pytest.raises(TypeError, match=r"overrides\.resources\.books\.report must be a BookResourceOverride"):
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(books={"report": "nope"}),  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match=r"overrides\.resources\.files\.detail_csv must be a FileResourceOverride"):
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(files={"detail_csv": "nope"}),  # type: ignore[arg-type]
        )


def test_run_overrides_resources_rejects_non_override_type_cover_branches() -> None:
    with pytest.raises(TypeError, match=r"RunOverrides\.resources must be a ResourcesOverride"):
        _ = RunOverrides(resources=object())  # type: ignore[arg-type]


def test_output_override_normalizes_fields_sequence_to_tuple_cover_branches() -> None:
    override = OutputOverride(name="detail", fields=["order_id", "amount"], to=OutputToOverride(file="detail_csv"))  # type: ignore[arg-type]
    assert isinstance(override.fields, tuple)
    assert override.fields == ("order_id", "amount")


def test_runtime_compiler_parse_non_empty_and_optional_path_or_init_var_cover_branches() -> None:
    assert compiler_mod._parse_non_empty_path_or_init_var({"$init_var": "p"}, path="p") == {"$init_var": "p"}  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p is required"):
        _ = compiler_mod._parse_non_empty_path_or_init_var(None, path="p")  # noqa: SLF001

    assert compiler_mod._parse_non_empty_path_or_init_var(_BlankPathLike(" x.xlsx "), path="p") == "x.xlsx"  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p is required"):
        _ = compiler_mod._parse_non_empty_path_or_init_var(_BlankPathLike("   "), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p is required"):
        _ = compiler_mod._parse_non_empty_path_or_init_var("   ", path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p must be a non-empty string"):
        _ = compiler_mod._parse_non_empty_path_or_init_var(1, path="p")  # noqa: SLF001

    assert compiler_mod._parse_optional_path_or_init_var(None, path="p") is None  # noqa: SLF001
    assert compiler_mod._parse_optional_path_or_init_var({"$init_var": "p"}, path="p") == {"$init_var": "p"}  # noqa: SLF001
    assert compiler_mod._parse_optional_path_or_init_var(_BlankPathLike(" x.xlsx "), path="p") == "x.xlsx"  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p must not be empty"):
        _ = compiler_mod._parse_optional_path_or_init_var(_BlankPathLike("   "), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p must not be empty"):
        _ = compiler_mod._parse_optional_path_or_init_var("   ", path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p must be a string"):
        _ = compiler_mod._parse_optional_path_or_init_var(1, path="p")  # noqa: SLF001


def test_runtime_compiler_normalize_non_empty_pathlike_value_cover_branches() -> None:
    assert compiler_mod._normalize_non_empty_pathlike_value(" x ", path="p") == "x"  # noqa: SLF001
    assert compiler_mod._normalize_non_empty_pathlike_value(_BlankPathLike(" x "), path="p") == "x"  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p is required"):
        _ = compiler_mod._normalize_non_empty_pathlike_value(None, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p is required"):
        _ = compiler_mod._normalize_non_empty_pathlike_value("   ", path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p must be a string or os\.PathLike"):
        _ = compiler_mod._normalize_non_empty_pathlike_value(1, path="p")  # noqa: SLF001


def test_runtime_compiler_parse_typed_overrides_output_write_cover_branches() -> None:
    with pytest.raises(TypeError, match=r"p\.include_header must be a boolean"):
        _ = compiler_mod._parse_typed_overrides_output_write(  # noqa: SLF001
            OutputWriteOverride(include_header="yes"),  # type: ignore[arg-type]
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.header_fields_output_by='nope' is invalid"):
        _ = compiler_mod._parse_typed_overrides_output_write(  # noqa: SLF001
            OutputWriteOverride(header_fields_output_by="nope"),
            path="p",
        )

    parsed = compiler_mod._parse_typed_overrides_output_write(  # noqa: SLF001
        OutputWriteOverride(include_header=True, header_fields_output_by=" name "),
        path="p",
    )
    assert parsed.include_header is True
    assert parsed.header_fields_output_by == "name"


def test_runtime_compiler_apply_file_override_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p\.kind='' is invalid"):
        _ = compiler_mod._apply_file_override(None, FileResourceOverride(), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind='json_file' is invalid"):
        _ = compiler_mod._apply_file_override(None, FileResourceOverride(kind="json_file"), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.path is required for kind=csv_file"):
        _ = compiler_mod._apply_file_override(None, FileResourceOverride(kind="csv_file"), path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.encoding must be a string"):
        _ = compiler_mod._apply_file_override(  # noqa: SLF001
            FileConfig(kind="csv_file", path="a.csv"),
            FileResourceOverride(encoding=1),  # type: ignore[arg-type]
            path="p",
        )

    patched = compiler_mod._apply_file_override(  # noqa: SLF001
        FileConfig(kind="csv_file", path="a.csv"),
        FileResourceOverride(encoding=" latin1 "),
        path="p",
    )
    assert patched.encoding == "latin1"

    created = compiler_mod._apply_file_override(None, FileResourceOverride(kind="csv_file", path="a.csv"), path="p")  # noqa: SLF001
    assert created.kind == "csv_file"
    assert created.path == "a.csv"


def test_runtime_compiler_apply_book_override_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p\.kind must be a non-empty string"):
        _ = compiler_mod._apply_book_override(None, BookResourceOverride(kind="  "), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind='json_file' is invalid"):
        _ = compiler_mod._apply_book_override(None, BookResourceOverride(kind="json_file"), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.path is required for kind=xlsx_file"):
        _ = compiler_mod._apply_book_override(None, BookResourceOverride(kind="xlsx_file"), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget/export_xlsx are not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            None,
            BookResourceOverride(
                kind="xlsx_file",
                path="a.xlsx",
                budget=BookBudgetOverride(max_sheets=1, max_total_cells=2),
            ),
            path="p",
        )

    with pytest.raises(ValueError, match=r"p\.budget is required for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_override(None, BookResourceOverride(kind="xlsx_memory"), path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.path/allow_formulas/write_lock are not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_override(  # noqa: SLF001
            None,
            BookResourceOverride(
                kind="xlsx_memory",
                path="x.xlsx",
                budget=BookBudgetOverride(max_sheets=1, max_total_cells=2),
            ),
            path="p",
        )

    created = compiler_mod._apply_book_override(  # noqa: SLF001
        None,
        BookResourceOverride(kind="xlsx_memory", budget=BookBudgetOverride(max_sheets=1, max_total_cells=2)),
        path="p",
    )
    assert created.kind == "xlsx_memory"
    assert created.budget is not None

    updated = compiler_mod._apply_book_override(  # noqa: SLF001
        BookConfig(kind="xlsx_file", path="a.xlsx"),
        BookResourceOverride(path="b.xlsx", allow_formulas=True, write_lock=True),
        path="p",
    )
    assert updated.path == "b.xlsx"
    assert updated.allow_formulas is True
    assert updated.write_lock is True


def test_runtime_compiler_apply_resources_override_and_io_overrides_cover_branches() -> None:
    base = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")},
            files={"detail": FileConfig(kind="csv_file", path="a.csv")},
        )
    )

    assert compiler_mod._apply_resources_override(base, ResourcesOverride()) == base  # noqa: SLF001

    merged = compiler_mod._apply_resources_override(  # noqa: SLF001
        base,
        ResourcesOverride(
            books={"report": BookResourceOverride(path="b.xlsx")},
            files={"detail": FileResourceOverride(path="b.csv")},
        ),
    )
    assert merged.resources is not None
    assert merged.resources.books["report"].path == "b.xlsx"
    assert merged.resources.files["detail"].path == "b.csv"

    with pytest.raises(ValueError, match=r"overrides\.resources\.books keys must be non-empty strings"):
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(books={1: BookResourceOverride(kind="xlsx_file", path="x.xlsx")}),  # type: ignore[dict-item]
        )

    options = RunOptions(
        allowed_modules=frozenset(["tests.fixtures"]),
        overrides=RunOverrides(resources=ResourcesOverride(files={"detail": FileResourceOverride(path="c.csv")})),
    )
    out = compiler_mod._apply_io_overrides(base, options=options)  # noqa: SLF001
    assert out.resources is not None
    assert out.resources.files["detail"].path == "c.csv"


def test_run_overrides_resources_legacy_dict_fail_fast() -> None:
    with pytest.raises(TypeError, match=r"Legacy YAML-shaped overrides are no longer supported: RunOverrides\.resources=dict"):
        _ = RunOverrides(resources={"files": {"detail": {"path": "x.csv"}}})  # type: ignore[arg-type]


def test_run_overrides_outputs_defaults_legacy_dict_fail_fast() -> None:
    with pytest.raises(
        TypeError,
        match=r"Legacy YAML-shaped overrides are no longer supported: RunOverrides\.outputs_defaults=dict",
    ):
        _ = RunOverrides(outputs_defaults={"to": {"book": "report"}})  # type: ignore[arg-type]
