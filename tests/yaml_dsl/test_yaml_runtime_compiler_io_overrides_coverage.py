import os

import pytest

from scalim.dsl.by_yaml.runtime import compiler as compiler_mod
from scalim.dsl.by_yaml.runtime.contracts import RunOptions, RunOverrides
from scalim.dsl.by_yaml.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    FileConfig,
    ResourcesConfig,
)
from scalim.spec.ir import DemandIr, FieldIr, MainSourceIr


class _BlankPathLike(os.PathLike):
    def __init__(self, value: str) -> None:
        self._value = str(value)

    def __fspath__(self) -> str:
        return self._value


def _dummy_main_loader(*_args, **_kwargs):  # type: ignore[no-untyped-def]
    return []


def _make_demand_ir() -> DemandIr:
    main = MainSourceIr(source_id="orders", loader=_dummy_main_loader)
    return DemandIr.from_irs(
        sources=[],
        fields=[FieldIr(field_id="order_id", name="order_id", source=main)],
        main_source=main,
        name="demo",
    )


def test_runtime_compiler_apply_file_patch_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p contains unknown keys"):
        _ = compiler_mod._apply_file_patch(None, {"nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind must be a non-empty string"):
        _ = compiler_mod._apply_file_patch(None, {"kind": ""}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind='json_file' is invalid"):
        _ = compiler_mod._apply_file_patch(None, {"kind": "json_file"}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.path is required for kind=csv_file"):
        _ = compiler_mod._apply_file_patch(None, {"kind": "csv_file"}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.encoding must be a string"):
        _ = compiler_mod._apply_file_patch(FileConfig(kind="csv_file", path="a.csv"), {"encoding": 1}, path="p")  # noqa: SLF001

    patched = compiler_mod._apply_file_patch(FileConfig(kind="csv_file", path="a.csv"), {"encoding": None}, path="p")  # noqa: SLF001
    assert patched.encoding

    patched = compiler_mod._apply_file_patch(FileConfig(kind="csv_file", path="a.csv"), {"encoding": " latin1 "}, path="p")  # noqa: SLF001
    assert patched.encoding == "latin1"

    patched = compiler_mod._apply_file_patch(None, {"kind": "csv_file", "path": "a.csv"}, path="p")  # noqa: SLF001
    assert patched.kind == "csv_file"
    assert patched.path == "a.csv"


def test_runtime_compiler_parse_overrides_to_and_write_cover_branches() -> None:
    with pytest.raises(ValueError, match=r"p has unknown keys"):
        _ = compiler_mod._parse_overrides_output_to({"book": "r", "nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.book must be a string"):
        _ = compiler_mod._parse_overrides_output_to({"book": 1}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.file must be a string"):
        _ = compiler_mod._parse_overrides_output_to({"file": 1}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.sheet must be a string"):
        _ = compiler_mod._parse_overrides_output_to({"sheet": 1}, path="p")  # noqa: SLF001

    assert compiler_mod._parse_overrides_output_to({"book": "   "}, path="p") is None  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p has unknown keys"):
        _ = compiler_mod._parse_overrides_output_write({"mode": "sheet", "nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.header_fields_output_by='nope' is invalid"):
        _ = compiler_mod._parse_overrides_output_write({"header_fields_output_by": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.include_header must be a boolean"):
        _ = compiler_mod._parse_overrides_output_write({"include_header": "yes"}, path="p")  # noqa: SLF001


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


def test_runtime_compiler_overlay_write_defaults_and_field_overlay_cover_branches() -> None:
    base = BookWriteDefaultsConfig(
        mode="sheet",
        align_by="field_id",
        header_policy="once",
        on_mismatch="error",
        on_conflict="error",
    )

    assert compiler_mod._overlay_optional_str_field({}, key="mode", value="x", path="p") == "x"  # noqa: SLF001
    assert compiler_mod._overlay_optional_str_field({"mode": None}, key="mode", value="x", path="p") == "x"  # noqa: SLF001
    with pytest.raises(TypeError, match=r"p\.mode must be a string"):
        _ = compiler_mod._overlay_optional_str_field({"mode": 1}, key="mode", value="x", path="p")  # noqa: SLF001
    assert compiler_mod._overlay_optional_str_field({"mode": " y "}, key="mode", value="x", path="p") == "y"  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p contains unknown keys"):
        _ = compiler_mod._overlay_book_write_defaults(base, {"nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.mode must be a string"):
        _ = compiler_mod._overlay_book_write_defaults(base, {"mode": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"Invalid write_defaults\.mode"):
        _ = compiler_mod._overlay_book_write_defaults(base, {"mode": "nope"}, path="p")  # noqa: SLF001

    out = compiler_mod._overlay_book_write_defaults(base, {}, path="p")  # noqa: SLF001
    assert out.mode == "sheet"


def test_runtime_compiler_apply_book_patch_cover_budget_export_and_semantic_branches() -> None:
    with pytest.raises(ValueError, match=r"p contains unknown keys"):
        _ = compiler_mod._apply_book_patch(None, {"nope": 1}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind must be a non-empty string"):
        _ = compiler_mod._apply_book_patch(None, {"kind": ""}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.allow_formulas must be a bool"):
        _ = compiler_mod._apply_book_patch(BookConfig(kind="xlsx_file", path="a.xlsx"), {"allow_formulas": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.write_lock must be a bool"):
        _ = compiler_mod._apply_book_patch(BookConfig(kind="xlsx_file", path="a.xlsx"), {"write_lock": "nope"}, path="p")  # noqa: SLF001

    patched = compiler_mod._apply_book_patch(
        BookConfig(kind="xlsx_file", path="a.xlsx"), {"allow_formulas": True, "write_lock": True}, path="p"
    )  # noqa: SLF001
    assert patched.allow_formulas is True
    assert patched.write_lock is True

    with pytest.raises(TypeError, match=r"p\.budget must be a mapping"):
        _ = compiler_mod._apply_book_patch(None, {"budget": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"requires max_sheets and max_total_cells"):
        _ = compiler_mod._apply_book_patch(None, {"budget": {"max_sheets": 1}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_sheets must be an integer"):
        _ = compiler_mod._apply_book_patch(None, {"budget": {"max_sheets": "nope", "max_total_cells": 1}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_total_cells must be an integer"):
        _ = compiler_mod._apply_book_patch(None, {"budget": {"max_sheets": 1, "max_total_cells": "nope"}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_sheets must be >= 1"):
        _ = compiler_mod._apply_book_patch(None, {"budget": {"max_sheets": 0, "max_total_cells": 1}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_total_cells must be >= 1"):
        _ = compiler_mod._apply_book_patch(None, {"budget": {"max_sheets": 1, "max_total_cells": 0}}, path="p")  # noqa: SLF001

    base_budget = BookBudgetConfig(max_sheets=2, max_total_cells=3)
    base = BookConfig(kind="xlsx_memory", budget=base_budget)
    with pytest.raises(ValueError, match=r"p\.budget\.max_sheets must be an integer"):
        _ = compiler_mod._apply_book_patch(base, {"budget": {"max_sheets": "nope"}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_total_cells must be an integer"):
        _ = compiler_mod._apply_book_patch(base, {"budget": {"max_total_cells": "nope"}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_sheets must be >= 1"):
        _ = compiler_mod._apply_book_patch(base, {"budget": {"max_sheets": 0}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.budget\.max_total_cells must be >= 1"):
        _ = compiler_mod._apply_book_patch(base, {"budget": {"max_total_cells": 0}}, path="p")  # noqa: SLF001

    patched = compiler_mod._apply_book_patch(base, {"budget": {"max_sheets": 4}}, path="p")  # noqa: SLF001
    assert patched.budget is not None
    assert patched.budget.max_sheets == 4

    with pytest.raises(TypeError, match=r"p\.export_xlsx must be a mapping"):
        _ = compiler_mod._apply_book_patch(None, {"export_xlsx": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.export_xlsx\.write_lock must be a bool"):
        _ = compiler_mod._apply_book_patch(None, {"export_xlsx": {"path": "x.xlsx", "write_lock": "nope"}}, path="p")  # noqa: SLF001

    with pytest.raises(TypeError, match=r"p\.export_xlsx\.allow_formulas must be a bool"):
        _ = compiler_mod._apply_book_patch(None, {"export_xlsx": {"path": "x.xlsx", "allow_formulas": "nope"}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"export_xlsx\.path is required"):
        _ = compiler_mod._apply_book_patch(None, {"export_xlsx": {}}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"p\.kind='' is invalid"):
        _ = compiler_mod._apply_book_patch(None, {"export_xlsx": {"path": "x.xlsx"}}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1))
    created = compiler_mod._apply_book_patch(base, {"export_xlsx": {"path": "x.xlsx"}}, path="p")  # noqa: SLF001
    assert created.export_xlsx is not None

    base_export = BookExportXlsxConfig(path="a.xlsx", write_lock=False, allow_formulas=False)
    base = BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1), export_xlsx=base_export)
    updated = compiler_mod._apply_book_patch(base, {"export_xlsx": {"path": "b.xlsx", "write_lock": True}}, path="p")  # noqa: SLF001
    assert updated.export_xlsx is not None
    assert updated.export_xlsx.path == "b.xlsx"
    assert updated.export_xlsx.write_lock is True

    cleared = compiler_mod._apply_book_patch(updated, {"export_xlsx": None}, path="p")  # noqa: SLF001
    assert cleared.export_xlsx is None

    with pytest.raises(TypeError, match=r"p\.write_defaults must be a mapping"):
        _ = compiler_mod._apply_book_patch(None, {"write_defaults": "nope"}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_file", path="a.xlsx")
    assert compiler_mod._apply_book_patch(base, {"write_defaults": None}, path="p").write_defaults is None  # noqa: SLF001

    patched = compiler_mod._apply_book_patch(base, {"write_defaults": {}}, path="p")  # noqa: SLF001
    assert patched.write_defaults is not None

    with pytest.raises(ValueError, match=r"p\.kind='nope' is invalid"):
        _ = compiler_mod._apply_book_patch(None, {"kind": "nope"}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"budget/export_xlsx are not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_patch(None, {"kind": "xlsx_file", "path": "a.xlsx", "budget": None}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"path is required for kind=xlsx_file"):
        _ = compiler_mod._apply_book_patch(None, {"kind": "xlsx_file"}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_memory", budget=BookBudgetConfig(max_sheets=1, max_total_cells=1))
    with pytest.raises(ValueError, match=r"budget is not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_patch(base, {"kind": "xlsx_file", "path": "a.xlsx"}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_file", path="a.xlsx", export_xlsx=BookExportXlsxConfig(path="x.xlsx"))
    with pytest.raises(ValueError, match=r"export_xlsx is not allowed for kind=xlsx_file"):
        _ = compiler_mod._apply_book_patch(base, {"kind": "xlsx_file", "path": "a.xlsx"}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"path/allow_formulas/write_lock are not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_patch(None, {"kind": "xlsx_memory", "path": "a.xlsx"}, path="p")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"budget is required for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_patch(None, {"kind": "xlsx_memory"}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_file", path="a.xlsx")
    with pytest.raises(ValueError, match=r"path is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_patch(base, {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_file", allow_formulas=True)
    with pytest.raises(ValueError, match=r"allow_formulas is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_patch(base, {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}}, path="p")  # noqa: SLF001

    base = BookConfig(kind="xlsx_file", write_lock=True)
    with pytest.raises(ValueError, match=r"write_lock is not allowed for kind=xlsx_memory"):
        _ = compiler_mod._apply_book_patch(base, {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}}, path="p")  # noqa: SLF001


def test_runtime_compiler_rejects_removed_outputs_defaults_override() -> None:
    with pytest.raises(TypeError, match=r"unexpected keyword argument 'outputs_defaults'"):
        _ = RunOverrides(outputs_defaults={"to": {"book": "report"}})  # type: ignore[call-arg]


def test_runtime_compiler_apply_resources_overrides_cover_branches() -> None:
    base = DemandConfig()

    with pytest.raises(TypeError, match=r"overrides\.resources must be an object"):
        _ = compiler_mod._apply_resources_io_override(base, "nope")  # noqa: SLF001

    with pytest.raises(ValueError, match=r"overrides\.resources has unknown keys"):
        _ = compiler_mod._apply_resources_io_override(base, {"nope": 1})  # noqa: SLF001

    assert compiler_mod._apply_resources_io_override(base, {"books": None}) == base  # noqa: SLF001
    assert compiler_mod._apply_resources_io_override(base, {"files": None}) == base  # noqa: SLF001

    with pytest.raises(TypeError, match=r"overrides\.resources\.books must be an object"):
        _ = compiler_mod._apply_resources_io_override(base, {"books": "nope"})  # noqa: SLF001

    with pytest.raises(ValueError, match=r"overrides\.resources\.books keys must be non-empty strings"):
        _ = compiler_mod._apply_resources_io_override(base, {"books": {"": {}}})  # noqa: SLF001

    with pytest.raises(TypeError, match=r"overrides\.resources\.books\.report must be an object"):
        _ = compiler_mod._apply_resources_io_override(base, {"books": {"report": "nope"}})  # noqa: SLF001

    with pytest.raises(TypeError, match=r"overrides\.resources\.files must be an object"):
        _ = compiler_mod._apply_resources_io_override(base, {"files": "nope"})  # noqa: SLF001

    with pytest.raises(ValueError, match=r"overrides\.resources\.files keys must be non-empty strings"):
        _ = compiler_mod._apply_resources_io_override(base, {"files": {"": {}}})  # noqa: SLF001

    with pytest.raises(TypeError, match=r"overrides\.resources\.files\.detail must be an object"):
        _ = compiler_mod._apply_resources_io_override(base, {"files": {"detail": "nope"}})  # noqa: SLF001

    merged = compiler_mod._apply_resources_io_override(base, {"books": {"report": {"kind": "xlsx_file", "path": "a.xlsx"}}})  # noqa: SLF001
    assert merged.resources is not None
    assert merged.resources.books["report"].kind == "xlsx_file"

    updated = compiler_mod._apply_resources_io_override(
        merged,
        {"books": {"report": {"path": "b.xlsx"}}},
    )  # noqa: SLF001
    assert updated.resources is not None
    assert updated.resources.books["report"].path == "b.xlsx"

    merged_files = compiler_mod._apply_resources_io_override(base, {"files": {"detail": {"kind": "csv_file", "path": "a.csv"}}})  # noqa: SLF001
    assert merged_files.resources is not None
    assert merged_files.resources.files["detail"].kind == "csv_file"


def test_runtime_compiler_apply_io_overrides_dispatch_covers_branches() -> None:
    cfg = DemandConfig(
        resources=ResourcesConfig(
            books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")}, files={"detail": FileConfig(kind="csv_file", path="a.csv")}
        ),
    )
    options = RunOptions(
        allowed_modules=frozenset(["tests.fixtures"]),
        overrides=RunOverrides(
            resources={"books": {"report": {"path": "b.xlsx"}}},
        ),
    )
    out = compiler_mod._apply_io_overrides(cfg, options=options)  # noqa: SLF001
    assert out.resources is not None
    assert out.resources.books["report"].path == "b.xlsx"

    options = RunOptions(
        allowed_modules=frozenset(["tests.fixtures"]),
        overrides=RunOverrides(
            resources={"files": {"detail": {"path": "b.csv"}}},
        ),
    )
    out = compiler_mod._apply_io_overrides(cfg, options=options)  # noqa: SLF001
    assert out.resources is not None
    assert out.resources.files["detail"].path == "b.csv"


def test_runtime_compiler_parse_overrides_outputs_targets_semantics_cover_branches() -> None:
    demand_ir = _make_demand_ir()

    with pytest.raises(ValueError, match=r"overrides\.outputs\.0\.to is required; declare exactly one of to\.file or to\.book"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [{"name": "detail", "to": {}, "fields": ["order_id"]}],
            demand_ir,
            path="overrides.outputs",
        )

    with pytest.raises(ValueError, match=r"overrides\.outputs\.0\.to\.sheet requires overrides\.outputs\.0\.to\.book"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [{"name": "detail", "to": {"file": "detail_csv", "sheet": "Detail"}, "fields": ["order_id"]}],
            demand_ir,
            path="overrides.outputs",
        )

    with pytest.raises(ValueError, match=r"align_by, header_policy, on_mismatch, on_conflict"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [
                {
                    "name": "detail",
                    "to": {"file": "detail_csv"},
                    "write": {"align_by": "field_id", "header_policy": "once", "on_mismatch": "warn", "on_conflict": "error"},
                    "fields": ["order_id"],
                }
            ],
            demand_ir,
            path="overrides.outputs",
        )

    with pytest.raises(ValueError, match=r"write\.include_header is not allowed for append-mode book outputs"):
        _ = compiler_mod._parse_overrides_outputs_targets(  # noqa: SLF001
            [{"name": "detail", "to": {"book": "report"}, "write": {"mode": "append", "include_header": True}, "fields": ["order_id"]}],
            demand_ir,
            path="overrides.outputs",
        )


def test_runtime_compiler_output_requires_unique_effective_names_cover_branches() -> None:
    from scalim.dsl.by_yaml.schema_dsl.models import OutputTargetConfig, OutputToConfig, OutputWriteConfig

    cfg = DemandConfig(resources=ResourcesConfig(books={"report": BookConfig(kind="xlsx_file", path="a.xlsx")}))
    assert (
        compiler_mod._output_requires_unique_effective_field_display_names(  # noqa: SLF001
            cfg,
            OutputTargetConfig(name="detail", to=OutputToConfig(sheet="Detail"), fields=("order_id",)),
        )
        is False
    )

    assert (
        compiler_mod._output_requires_unique_effective_field_display_names(  # noqa: SLF001
            cfg,
            OutputTargetConfig(
                name="detail",
                to=OutputToConfig(book="report", sheet="Detail"),
                write=OutputWriteConfig(mode="sheet", include_header=False),
                fields=("order_id",),
            ),
        )
        is False
    )
