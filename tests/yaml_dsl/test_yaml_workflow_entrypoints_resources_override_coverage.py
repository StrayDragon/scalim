from scalim.dsl.by_yaml import workflow_entrypoints as entrypoints_mod
from scalim.dsl.by_yaml.runtime.contracts import RunOverrides
from scalim.dsl.by_yaml.schema_dsl.models import BookBudgetConfig, BookConfig, BookExportXlsxConfig, FileConfig, ResourcesConfig
from scalim.dsl.by_yaml.workflow import WorkflowConfig, WorkflowOptions


def test_workflow_entrypoints_deep_merge_dicts_recurses_and_overwrites() -> None:
    merged = entrypoints_mod._deep_merge_dicts(  # noqa: SLF001
        {"a": {"x": 1}, "b": 1},
        {"a": {"y": 2}, "b": 2},
    )
    assert merged == {"a": {"x": 1, "y": 2}, "b": 2}


def test_workflow_entrypoints_resource_override_patch_builders_cover_branches() -> None:
    patch = entrypoints_mod._book_config_to_override_patch(  # noqa: SLF001
        BookConfig(kind="xlsx_file", path="a.xlsx", allow_formulas=True, write_lock=True)
    )
    assert patch["allow_formulas"] is True

    patch2 = entrypoints_mod._book_config_to_override_patch(  # noqa: SLF001
        BookConfig(
            kind="xlsx_memory",
            budget=BookBudgetConfig(max_sheets=1, max_total_cells=2),
            export_xlsx=BookExportXlsxConfig(path="x.xlsx", allow_formulas=True, write_lock=True),
        )
    )
    assert patch2["export_xlsx"]["allow_formulas"] is True

    file_patch = entrypoints_mod._file_config_to_override_patch(FileConfig(kind="csv_file", path="a.csv", encoding="utf-8"))  # noqa: SLF001
    assert file_patch["path"] == "a.csv"
    assert file_patch["encoding"] == "utf-8"


def test_workflow_entrypoints_workflow_resources_override_patch_handles_missing_and_files() -> None:
    wf = WorkflowConfig(runs=(), options=WorkflowOptions(), resources="nope")  # type: ignore[arg-type]
    assert entrypoints_mod._workflow_resources_override_patch(wf) is None  # noqa: SLF001

    wf2 = WorkflowConfig(
        runs=(),
        options=WorkflowOptions(),
        resources=ResourcesConfig(files={"detail_csv": FileConfig(kind="csv_file", path="a.csv", encoding="utf-8")}),
    )
    out = entrypoints_mod._workflow_resources_override_patch(wf2)  # noqa: SLF001
    assert out is not None
    assert "files" in out


def test_workflow_entrypoints_merge_node_overrides_deep_merges_resources() -> None:
    merged = entrypoints_mod._merge_node_overrides(  # noqa: SLF001
        RunOverrides(resources={"files": {"detail_csv": {"path": "a.csv"}}}),
        workflow_resources_patch={"files": {"detail_csv": {"encoding": "utf-8"}}},
    )
    assert merged is not None
    assert merged.resources == {"files": {"detail_csv": {"path": "a.csv", "encoding": "utf-8"}}}
