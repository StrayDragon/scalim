import os

import pytest

from scalim.dsl.yaml_dsl._internal import resource_override as resource_override_mod
from scalim.dsl.yaml_dsl.init_var_nodes import InitVarRef
from scalim.dsl.yaml_dsl.runtime import compiler as compiler_mod
from scalim.dsl.yaml_dsl.runtime import effective_outputs as effective_outputs_mod
from scalim.workflow.errors import ScalimWorkflowConfigError
from scalim.dsl.yaml_dsl import workflow_compile as workflow_compile_mod
from scalim.dsl.yaml_dsl.runtime.contracts import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookResourceOverride,
    BookWriteDefaultsOverride,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunSecurityOptions,
    FileResourceOverride,
    OutputDefaultsToOverride,
    OutputsDefaultsOverride,
    OutputOverride,
    OutputToOverride,
    OutputWriteOverride,
    ResourcesOverride,
    RunOverrides,
)
from scalim.dsl.yaml_dsl.schema_dsl.models import (
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

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_defaults_book_id(object(), path="p")  # type: ignore[arg-type]  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(TypeError, match=r"OutputsDefaultsOverride\.to must be an OutputDefaultsToOverride"):
        _ = OutputsDefaultsOverride(to=object())  # type: ignore[arg-type]

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_defaults_book_id(  # noqa: SLF001
            OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="   ")),
            path="p",
        )
    assert exc_info.value.path == "p.to.book"

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

    parsed = resource_override_mod._parse_typed_overrides_output_to(raw)  # noqa: SLF001
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
    options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures"])),
        outputs=DemandRunOutputOptions(
            overrides=RunOverrides(outputs_defaults=OutputsDefaultsOverride(to=OutputDefaultsToOverride(book="report")))
        ),
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

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # type: ignore[arg-type]  # noqa: SLF001
            object(),
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # type: ignore[list-item]  # noqa: SLF001
            [object()],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0"

    out_cfg = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"))
    object.__setattr__(out_cfg, "fields", ["order_id"])
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_cfg],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.fields"

    out_bad_field_type = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"))
    object.__setattr__(out_bad_field_type, "fields", (1,))  # type: ignore[assignment]
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_field_type],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.fields.0"

    out_empty_field = OutputOverride(name="detail", fields=("   ",), to=OutputToOverride(file="detail_csv"))
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_empty_field],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.fields.0"

    out_bad_to = OutputOverride(name="detail", fields=("order_id",), to=object())  # type: ignore[arg-type]
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_to],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.to"

    out_bad_write = OutputOverride(name="detail", fields=("order_id",), to=OutputToOverride(file="detail_csv"), write=object())  # type: ignore[arg-type]
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_bad_write],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.write"

    out_file_with_sheet = OutputOverride(
        name="detail",
        fields=("order_id",),
        to=OutputToOverride(file="detail_csv", sheet="S"),
    )
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [out_file_with_sheet],
            demand_ir,  # type: ignore[arg-type]
            path="p",
            default_book_id=None,
            default_book_ref="ref",
        )
    assert exc_info.value.path == "p.0.to.sheet"


def test_runtime_compiler_output_requires_unique_effective_field_display_names_cover_branches() -> None:
    out_cfg = OutputTargetConfig(
        name="detail",
        to=OutputToConfig(book="  "),
        write=OutputWriteConfig(header_fields_output_by="name"),
        fields=("order_id",),
    )
    assert (
        effective_outputs_mod.output_target_requires_unique_effective_field_display_names(
            DemandConfig(),
            out_cfg,
            resources_override=None,
        )
        is False
    )


def test_runtime_compiler_overlay_book_write_defaults_override_invalid_enum_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"Invalid write_defaults\.mode") as exc_info:
        _ = resource_override_mod.apply_book_resource_override(
            BookConfig(kind="xlsx_file", path="a"),
            BookResourceOverride(write_defaults=BookWriteDefaultsOverride(mode="nope")),
            path="p",
        )
    assert exc_info.value.path == "p.write_defaults.mode"


def test_runtime_compiler_overlay_book_budget_override_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"requires max_sheets and max_total_cells") as exc_info:
        _ = resource_override_mod._apply_optional_book_budget_patch(  # noqa: SLF001
            None,
            {"max_total_cells": 2},
            path="p",
        )
    assert exc_info.value.path == "p.budget"

    base_budget = BookBudgetConfig(max_sheets=1, max_total_cells=2)
    merged = resource_override_mod._apply_optional_book_budget_patch(  # noqa: SLF001
        base_budget,
        {"max_total_cells": 3},
        path="p",
    )
    assert merged is not None
    assert merged.max_sheets == 1
    assert merged.max_total_cells == 3

    with pytest.raises(ScalimWorkflowConfigError, match=r"must be an integer") as exc_info:
        _ = resource_override_mod._apply_optional_book_budget_patch(None, {"max_sheets": True, "max_total_cells": 2}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget.max_sheets"

    with pytest.raises(ScalimWorkflowConfigError, match=r"must be an integer") as exc_info:
        _ = resource_override_mod._apply_optional_book_budget_patch(None, {"max_sheets": 1, "max_total_cells": True}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget.max_total_cells"

    with pytest.raises(ScalimWorkflowConfigError, match=r"must be >= 1") as exc_info:
        _ = resource_override_mod._apply_optional_book_budget_patch(None, {"max_sheets": 0, "max_total_cells": 2}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget.max_sheets"

    with pytest.raises(ScalimWorkflowConfigError, match=r"must be >= 1") as exc_info:
        _ = resource_override_mod._apply_optional_book_budget_patch(None, {"max_sheets": 1, "max_total_cells": 0}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.budget.max_total_cells"


def test_runtime_compiler_overlay_book_export_xlsx_override_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError, match=r"export_xlsx\.path is required when creating export_xlsx") as exc_info:
        _ = resource_override_mod._apply_optional_book_export_xlsx_patch(None, {}, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.export_xlsx.path"

    base = BookExportXlsxConfig(path="a", allow_formulas=False)
    updated = resource_override_mod._apply_optional_book_export_xlsx_patch(  # noqa: SLF001
        base,
        {"path": "b", "allow_formulas": True},
        path="p",
    )
    assert updated is not None
    assert updated.path == "b"
    assert updated.allow_formulas is True

    updated2 = resource_override_mod._apply_optional_book_export_xlsx_patch(  # noqa: SLF001
        base,
        {},
        path="p",
    )
    assert updated2 is not None
    assert updated2.path == "a"
    assert updated2.allow_formulas is False


def test_runtime_compiler_apply_book_override_semantic_and_type_errors_cover_branches() -> None:
    base_file = BookConfig(kind="xlsx_file", path="a")
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            base_file,
            BookResourceOverride(allow_formulas="yes"),  # type: ignore[arg-type]
            path="p",
        )
    assert exc_info.value.path == "p.allow_formulas"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            BookConfig(kind="xlsx_file", path="a", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1)),
            BookResourceOverride(),
            path="p",
        )
    assert exc_info.value.path == "p.budget"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            BookConfig(
                kind="xlsx_file",
                path="a",
                export_xlsx=BookExportXlsxConfig(path="x", allow_formulas=False),
            ),
            BookResourceOverride(),
            path="p",
        )
    assert exc_info.value.path == "p.export_xlsx"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            BookConfig(kind="xlsx_memory", path="a", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1)),
            BookResourceOverride(),
            path="p",
        )
    assert exc_info.value.path == "p.path"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            BookConfig(
                kind="xlsx_memory",
                budget=BookBudgetConfig(max_sheets=1, max_total_cells=1),
                allow_formulas=True,
            ),
            BookResourceOverride(),
            path="p",
        )
    assert exc_info.value.path == "p.allow_formulas"


def test_runtime_compiler_apply_file_override_non_empty_kind_validation_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_file_resource_override(  # noqa: SLF001
            FileConfig(kind="csv_file", path="a"),
            FileResourceOverride(kind="  "),
            path="p",
        )
    assert exc_info.value.path == "p.kind"


def test_runtime_compiler_apply_resources_override_type_checks_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(books={"report": "nope"}),  # type: ignore[arg-type]
        )
    assert exc_info.value.path == "overrides.resources.books.report"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(files={"detail_csv": "nope"}),  # type: ignore[arg-type]
        )
    assert exc_info.value.path == "overrides.resources.files.detail_csv"


def test_run_overrides_resources_rejects_non_override_type_cover_branches() -> None:
    with pytest.raises(TypeError, match=r"RunOverrides\.resources must be a ResourcesOverride"):
        _ = RunOverrides(resources=object())  # type: ignore[arg-type]


def test_output_override_normalizes_fields_sequence_to_tuple_cover_branches() -> None:
    override = OutputOverride(name="detail", fields=["order_id", "amount"], to=OutputToOverride(file="detail_csv"))  # type: ignore[arg-type]
    assert isinstance(override.fields, tuple)
    assert override.fields == ("order_id", "amount")


def test_resource_override_as_opt_path_or_init_var_cover_branches() -> None:
    out = resource_override_mod._as_opt_path_or_init_var({"$init_var": "p"}, path="p")  # noqa: SLF001
    assert isinstance(out, InitVarRef)
    assert out.name == "p"
    assert out.path == "p"
    assert resource_override_mod._as_opt_path_or_init_var(None, path="p") is None  # noqa: SLF001
    assert resource_override_mod._as_opt_path_or_init_var(_BlankPathLike(" x "), path="p") == "x"  # noqa: SLF001

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_path_or_init_var(_BlankPathLike("   "), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_path_or_init_var("   ", path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_path_or_init_var(1, path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"


def test_resource_override_as_opt_path_or_init_var_rejects_empty_strings_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._as_opt_path_or_init_var("", path="p")  # noqa: SLF001
    assert exc_info.value.path == "p"


def test_runtime_compiler_parse_typed_overrides_output_write_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._parse_typed_overrides_output_write(  # noqa: SLF001
            OutputWriteOverride(include_header="yes"),  # type: ignore[arg-type]
            path="p",
        )
    assert exc_info.value.path == "p.include_header"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod._parse_typed_overrides_output_write(  # noqa: SLF001
            OutputWriteOverride(header_fields_output_by="nope"),
            path="p",
        )
    assert exc_info.value.path == "p.header_fields_output_by"

    parsed = resource_override_mod._parse_typed_overrides_output_write(  # noqa: SLF001
        OutputWriteOverride(include_header=True, header_fields_output_by=" name "),
        path="p",
    )
    assert parsed.include_header is True
    assert parsed.header_fields_output_by == "name"


def test_runtime_compiler_apply_file_override_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_file_resource_override(None, FileResourceOverride(), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_file_resource_override(None, FileResourceOverride(kind="json_file"), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_file_resource_override(None, FileResourceOverride(kind="csv_file"), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.path"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_file_resource_override(  # noqa: SLF001
            FileConfig(kind="csv_file", path="a"),
            FileResourceOverride(encoding=1),  # type: ignore[arg-type]
            path="p",
        )
    assert exc_info.value.path == "p.encoding"

    patched = resource_override_mod.apply_file_resource_override(  # noqa: SLF001
        FileConfig(kind="csv_file", path="a"),
        FileResourceOverride(encoding=" latin1 "),
        path="p",
    )
    assert patched.encoding == "latin1"

    created = resource_override_mod.apply_file_resource_override(None, FileResourceOverride(kind="csv_file", path="a"), path="p")  # noqa: SLF001
    assert created.kind == "csv_file"
    assert created.path == "a"


def test_runtime_compiler_apply_book_override_cover_branches() -> None:
    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(None, BookResourceOverride(kind="  "), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(None, BookResourceOverride(kind="json_file"), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.kind"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(None, BookResourceOverride(kind="xlsx_file"), path="p")  # noqa: SLF001
    assert exc_info.value.path == "p.path"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            None,
            BookResourceOverride(
                kind="xlsx_file",
                path="a",
                budget=BookBudgetOverride(max_sheets=1, max_total_cells=2),
            ),
            path="p",
        )
    assert exc_info.value.path == "p.budget"

    created_unlimited = resource_override_mod.apply_book_resource_override(None, BookResourceOverride(kind="xlsx_memory"), path="p")  # noqa: SLF001
    assert created_unlimited.kind == "xlsx_memory"
    assert created_unlimited.budget is None

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            None,
            BookResourceOverride(
                kind="xlsx_memory",
                budget=BookBudgetOverride(max_sheets=0, max_total_cells=2),
            ),
            path="p",
        )
    assert exc_info.value.path == "p.budget.max_sheets"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
            None,
            BookResourceOverride(
                kind="xlsx_memory",
                path="x",
                budget=BookBudgetOverride(max_sheets=1, max_total_cells=2),
            ),
            path="p",
        )
    assert exc_info.value.path == "p.path"

    created = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
        None,
        BookResourceOverride(kind="xlsx_memory", budget=BookBudgetOverride(max_sheets=1, max_total_cells=2)),
        path="p",
    )
    assert created.kind == "xlsx_memory"
    assert created.budget is not None

    updated = resource_override_mod.apply_book_resource_override(  # noqa: SLF001
        BookConfig(kind="xlsx_file", path="a"),
        BookResourceOverride(path="b", allow_formulas=True),
        path="p",
    )
    assert updated.path == "b"
    assert updated.allow_formulas is True


def test_runtime_compiler_apply_resources_override_and_io_overrides_cover_branches() -> None:
    base = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="a")},
            files={"detail": FileConfig(kind="csv_file", path="a")},
        )
    )

    assert compiler_mod._apply_resources_override(base, ResourcesOverride()) == base  # noqa: SLF001

    merged = compiler_mod._apply_resources_override(  # noqa: SLF001
        base,
        ResourcesOverride(
            books={"report": BookResourceOverride(path="b")},
            files={"detail": FileResourceOverride(path="b")},
        ),
    )
    assert merged.resources is not None
    assert merged.resources.books["report"].path == "b"
    assert merged.resources.files["detail"].path == "b"

    with pytest.raises(ScalimWorkflowConfigError) as exc_info:
        _ = compiler_mod._apply_resources_override(  # noqa: SLF001
            DemandConfig(),
            ResourcesOverride(books={1: BookResourceOverride(kind="xlsx_file", path="x")}),  # type: ignore[dict-item]
        )
    assert exc_info.value.path == "overrides.resources.books"

    options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=frozenset(["tests.fixtures"])),
        outputs=DemandRunOutputOptions(
            overrides=RunOverrides(resources=ResourcesOverride(files={"detail": FileResourceOverride(path="c")}))
        ),
    )
    out = compiler_mod._apply_io_overrides(base, options=options)  # noqa: SLF001
    assert out.resources is not None
    assert out.resources.files["detail"].path == "c"


def test_run_overrides_resources_legacy_dict_fail_fast() -> None:
    with pytest.raises(TypeError, match=r"Legacy YAML-shaped overrides are no longer supported: RunOverrides\.resources=dict"):
        _ = RunOverrides(resources={"files": {"detail": {"path": "x"}}})  # type: ignore[arg-type]


def test_run_overrides_outputs_defaults_legacy_dict_fail_fast() -> None:
    with pytest.raises(
        TypeError,
        match=r"Legacy YAML-shaped overrides are no longer supported: RunOverrides\.outputs_defaults=dict",
    ):
        _ = RunOverrides(outputs_defaults={"to": {"book": "report"}})  # type: ignore[arg-type]


def test_invalid_output_overrides_fail_consistently_across_entrypoints_regression() -> None:
    class _FakeDemandIr:
        fields = ("a",)

    invalid = [OutputOverride(name="detail", fields=("a",), to=OutputToOverride(file="f", sheet="S"))]
    with pytest.raises(ScalimWorkflowConfigError) as demand_exc_info:
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            invalid,
            _FakeDemandIr(),  # type: ignore[arg-type]
            path="overrides.outputs",
            default_book_id=None,
            default_book_ref="overrides.outputs_defaults.to.book",
        )

    with pytest.raises(ScalimWorkflowConfigError) as workflow_exc_info:
        _ = workflow_compile_mod._effective_outputs_for_workflow_compile(  # noqa: SLF001
            DemandConfig(),
            overrides_outputs=invalid,
            default_book_id=None,
        )

    assert type(demand_exc_info.value) is type(workflow_exc_info.value)
    assert demand_exc_info.value.path == workflow_exc_info.value.path
