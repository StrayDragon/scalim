from scalim.dsl.yaml_dsl import (
    BookBudgetOverride,
    BookExportXlsxOverride,
    BookWriteDefaultsOverride,
    BookResourceOverride,
    FileResourceOverride,
    ResourcesOverride,
    RunOverrides,
)
from scalim.dsl.yaml_dsl import workflow_entrypoints as entrypoints_mod
from scalim.dsl.yaml_dsl.schema_dsl.models import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    FileConfig,
    ResourcesConfig,
)
from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, WorkflowOptions


def test_workflow_entrypoints_merge_book_override_helpers_cover_branches() -> None:
    left_budget = BookBudgetOverride(max_sheets=1, max_total_cells=2)
    right_budget = BookBudgetOverride(max_sheets=None, max_total_cells=3)
    assert entrypoints_mod._merge_book_budget_overrides(left_budget, None) == left_budget  # noqa: SLF001
    assert entrypoints_mod._merge_book_budget_overrides(None, right_budget) == right_budget  # noqa: SLF001
    merged_budget = entrypoints_mod._merge_book_budget_overrides(left_budget, right_budget)  # noqa: SLF001
    assert merged_budget is not None
    assert merged_budget.max_sheets == 1
    assert merged_budget.max_total_cells == 3

    left_export = BookExportXlsxOverride(path="a.xlsx")
    right_export = BookExportXlsxOverride(path=None, write_lock=True, allow_formulas=True)
    assert entrypoints_mod._merge_book_export_xlsx_overrides(left_export, None) == left_export  # noqa: SLF001
    assert entrypoints_mod._merge_book_export_xlsx_overrides(None, right_export) == right_export  # noqa: SLF001
    merged_export = entrypoints_mod._merge_book_export_xlsx_overrides(left_export, right_export)  # noqa: SLF001
    assert merged_export is not None
    assert merged_export.path == "a.xlsx"
    assert merged_export.write_lock is True
    assert merged_export.allow_formulas is True

    left_write = BookWriteDefaultsOverride(mode="append")
    right_write = BookWriteDefaultsOverride(mode=None, align_by="name")
    assert entrypoints_mod._merge_book_write_defaults_overrides(left_write, None) == left_write  # noqa: SLF001
    assert entrypoints_mod._merge_book_write_defaults_overrides(None, right_write) == right_write  # noqa: SLF001
    merged_write = entrypoints_mod._merge_book_write_defaults_overrides(left_write, right_write)  # noqa: SLF001
    assert merged_write is not None
    assert merged_write.mode == "append"
    assert merged_write.align_by == "name"

    left_book = BookResourceOverride(kind="xlsx_file", path="a.xlsx", allow_formulas=True)
    right_book = BookResourceOverride(path="b.xlsx", allow_formulas=None)
    assert entrypoints_mod._merge_book_resource_overrides(None, right_book) is right_book  # noqa: SLF001
    merged_book = entrypoints_mod._merge_book_resource_overrides(left_book, right_book)  # noqa: SLF001
    assert merged_book.kind == "xlsx_file"
    assert merged_book.path == "b.xlsx"
    assert merged_book.allow_formulas is True

    left_file = FileResourceOverride(kind="csv_file", path="a.csv", encoding="utf-8")
    right_file = FileResourceOverride(path="b.csv")
    assert entrypoints_mod._merge_file_resource_overrides(None, right_file) is right_file  # noqa: SLF001
    merged_file = entrypoints_mod._merge_file_resource_overrides(left_file, right_file)  # noqa: SLF001
    assert merged_file.kind == "csv_file"
    assert merged_file.path == "b.csv"
    assert merged_file.encoding == "utf-8"

    merged_resources = entrypoints_mod._merge_resources_overrides(  # noqa: SLF001
        ResourcesOverride(books={"report": left_book}),
        ResourcesOverride(books={"report": right_book}),
    )
    assert merged_resources is not None
    assert merged_resources.books is not None
    assert merged_resources.books["report"].path == "b.xlsx"


def test_workflow_entrypoints_workflow_resources_override_handles_missing_and_converts() -> None:
    wf = WorkflowConfig(runs=(), options=WorkflowOptions(), resources="nope")  # type: ignore[arg-type]
    assert entrypoints_mod._workflow_resources_override(wf) is None  # noqa: SLF001

    wf_empty = WorkflowConfig(runs=(), options=WorkflowOptions(), resources=ResourcesConfig())
    assert entrypoints_mod._workflow_resources_override(wf_empty) is None  # noqa: SLF001

    wf2 = WorkflowConfig(
        runs=(),
        options=WorkflowOptions(),
        resources=ResourcesConfig(
            books={
                "report": BookConfig(
                    kind="xlsx_file",
                    path="a.xlsx",
                    allow_formulas=True,
                    write_lock=True,
                    write_defaults=BookWriteDefaultsConfig(mode="append"),
                ),
                "mem": BookConfig(
                    kind="xlsx_memory",
                    budget=BookBudgetConfig(max_sheets=1, max_total_cells=2),
                    export_xlsx=BookExportXlsxConfig(path="x.xlsx", allow_formulas=True, write_lock=True),
                ),
            },
            files={"detail_csv": FileConfig(kind="csv_file", path="a.csv", encoding="utf-8")},
        ),
    )
    out = entrypoints_mod._workflow_resources_override(wf2)  # noqa: SLF001
    assert out is not None
    assert out.books is not None
    assert out.books["report"].allow_formulas is True
    assert out.books["report"].write_lock is True
    assert out.books["report"].write_defaults is not None
    assert out.books["report"].write_defaults.mode == "append"
    assert out.books["mem"].budget is not None
    assert out.books["mem"].export_xlsx is not None
    assert out.books["mem"].export_xlsx.allow_formulas is True
    assert out.books["mem"].export_xlsx.write_lock is True
    assert out.files is not None
    assert out.files["detail_csv"].encoding == "utf-8"


def test_workflow_entrypoints_merge_node_overrides_deep_merges_resources() -> None:
    workflow_resources_override = ResourcesOverride(
        files={"detail_csv": FileResourceOverride(kind="csv_file", path="wf.csv", encoding="utf-8")}
    )
    base = RunOverrides(resources=ResourcesOverride(files={"detail_csv": FileResourceOverride(path="a.csv")}))

    merged = entrypoints_mod._merge_node_overrides(base, workflow_resources_override=workflow_resources_override)  # noqa: SLF001
    assert merged is not None
    assert merged.resources is not None
    assert merged.resources.files is not None
    assert merged.resources.files["detail_csv"].path == "a.csv"
    assert merged.resources.files["detail_csv"].encoding == "utf-8"

    merged2 = entrypoints_mod._merge_node_overrides(None, workflow_resources_override=workflow_resources_override)  # noqa: SLF001
    assert merged2 is not None
    assert merged2.resources == workflow_resources_override

    same = entrypoints_mod._merge_node_overrides(base, workflow_resources_override=None)  # noqa: SLF001
    assert same is base
