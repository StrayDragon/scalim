import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from scalim.dsl.by_yaml.workflow import ScalimWorkflowConfigError, load_workflow_config, load_workflow_config_from_mapping


def _base_root() -> Dict[str, Any]:
    return {
        "workflow": {
            "runs": [
                {
                    "id": "a",
                    "demand": "a.yaml",
                }
            ]
        }
    }


def test_workflow_yaml_duplicate_keys_fail_fast(tmp_path: Path) -> None:
    workflow_path = tmp_path / "wf.yaml"
    workflow_path.write_text(
        (
            """
workflow:
  runs:
    - id: a
      demand: a.yaml
  resources:
    workbooks:
      report:
        path: ./a.xlsx
      report:
        path: ./b.xlsx
"""
        ).lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "Duplicate key" in str(excinfo.value)


def test_workflow_run_id_rejects_internal_prefix() -> None:
    root = _base_root()
    root["workflow"]["runs"][0]["id"] = "__wf__bad"
    with pytest.raises(ScalimWorkflowConfigError, match="reserved prefix"):
        _ = load_workflow_config_from_mapping(root)


@pytest.mark.parametrize(
    ("writes_raw", "match"),
    [
        ("nope", "run.writes must be a list of intents"),
        (["nope"], "write intent must be a mapping"),
        ([{1: {}}], "write intent keys must be non-empty strings"),
        ([{}], "write intent must contain exactly one of"),
        ([{"workbook_sheet": {}, "csv_append": {}}], "write intent must contain exactly one of"),
        ([{"nope": {}}], "write intent contains unknown key"),
        ([{"workbook_sheet": "nope"}], "run.writes.workbook_sheet must be a mapping"),
        ([{"workbook_sheet": {1: "nope"}}], "run.writes.workbook_sheet keys must be non-empty strings"),
        ([{"workbook_sheet": {"sheet": "S", "output": "o"}}], "run.writes.workbook_sheet.workbook must be a non-empty string"),
        ([{"workbook_sheet": {"workbook": "r", "output": "o"}}], "run.writes.workbook_sheet.sheet must be a non-empty string"),
        ([{"workbook_sheet": {"workbook": "r", "sheet": "S"}}], "run.writes.workbook_sheet.output must be a non-empty string"),
        (
            [{"workbook_sheet": {"workbook": "r", "sheet": "S", "output": "o", "on_conflict": "bad"}}],
            "run.writes.workbook_sheet.on_conflict must be one of",
        ),
        ([{"workbook_append": {"sheet": "S", "output": "o"}}], "run.writes.workbook_append.workbook must be a non-empty string"),
        ([{"workbook_append": {"workbook": "r", "output": "o"}}], "run.writes.workbook_append.sheet must be a non-empty string"),
        ([{"workbook_append": {"workbook": "r", "sheet": "S"}}], "run.writes.workbook_append.output must be a non-empty string"),
        (
            [{"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "align_by": "bad"}}],
            "run.writes.workbook_append.align_by must be one of",
        ),
        (
            [{"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "header_policy": "bad"}}],
            "run.writes.workbook_append.header_policy must be one of",
        ),
        (
            [{"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "on_mismatch": "bad"}}],
            "run.writes.workbook_append.on_mismatch must be one of",
        ),
        ([{"csv_append": {"output": "o"}}], "run.writes.csv_append.csv must be a non-empty string"),
        ([{"csv_append": {"csv": "c"}}], "run.writes.csv_append.output must be a non-empty string"),
        ([{"csv_append": {"csv": "c", "output": "o", "header_policy": "bad"}}], "run.writes.csv_append.header_policy must be one of"),
        ([{"csv_append": {"csv": "c", "output": "o", "on_mismatch": "bad"}}], "run.writes.csv_append.on_mismatch must be one of"),
        ([{"sheetbook_sheet": {"sheet": "S", "output": "o"}}], "run.writes.sheetbook_sheet.sheetbook must be a non-empty string"),
        ([{"sheetbook_sheet": {"sheetbook": "sb", "output": "o"}}], "sheet name must be a non-empty string"),
        ([{"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S"}}], "run.writes.sheetbook_sheet.output must be a non-empty string"),
        ([{"sheetbook_sheet": {"sheetbook": "sb", "sheet": "Bad:Name", "output": "o"}}], "invalid characters"),
        ([{"sheetbook_sheet": {"sheetbook": "sb", "sheet": "x" * 32, "output": "o"}}], "too long"),
        (
            [{"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S", "output": "o", "on_conflict": "bad"}}],
            "run.writes.sheetbook_sheet.on_conflict must be one of",
        ),
        ([{"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S", "output": "o"}}], "Unknown sheetbook resource id"),
        ([{"sheetbook_append": {"sheet": "S", "output": "o"}}], "run.writes.sheetbook_append.sheetbook must be a non-empty string"),
        ([{"sheetbook_append": {"sheetbook": "sb", "sheet": "S"}}], "run.writes.sheetbook_append.output must be a non-empty string"),
        (
            [{"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "align_by": "bad"}}],
            "run.writes.sheetbook_append.align_by must be one of",
        ),
        (
            [{"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "header_policy": "bad"}}],
            "run.writes.sheetbook_append.header_policy must be one of",
        ),
        (
            [{"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "on_mismatch": "bad"}}],
            "run.writes.sheetbook_append.on_mismatch must be one of",
        ),
    ],
)
def test_load_workflow_config_from_mapping_writes_errors(writes_raw: Any, match: str) -> None:
    root = _base_root()
    root["workflow"]["runs"][0]["writes"] = writes_raw
    with pytest.raises(ScalimWorkflowConfigError, match=match):
        _ = load_workflow_config_from_mapping(root)


@pytest.mark.parametrize(
    ("resources_raw", "match"),
    [
        ({"oops": {}}, "contains unknown keys"),
        ({"workbooks": "nope"}, "workbooks must be a mapping"),
        ({"csvs": "nope"}, "csvs must be a mapping"),
        ({"sheetbooks": "nope"}, "sheetbooks must be a mapping"),
        ({"workbooks": {1: {"path": "a.xlsx"}}}, "workbooks keys must be non-empty strings"),
        ({"workbooks": {"report": "nope"}}, "workbooks.<id> must be a mapping"),
        ({"workbooks": {"report": {}}}, "workbooks.<id>.path must be a non-empty string"),
        ({"workbooks": {"report": {"path": "a.xlsx", "allow_formulas": "nope"}}}, "allow_formulas must be a bool"),
        ({"csvs": {1: {"path": "a.csv"}}}, "csvs keys must be non-empty strings"),
        ({"csvs": {"merged": "nope"}}, "csvs.<id> must be a mapping"),
        ({"csvs": {"merged": {}}}, "csvs.<id>.path must be a non-empty string"),
        ({"sheetbooks": {1: {"budget": {"max_sheets": 1, "max_total_cells": 1}}}}, "sheetbooks keys must be non-empty strings"),
        ({"sheetbooks": {"sb": "nope"}}, "sheetbooks.<id> must be a mapping"),
        ({"sheetbooks": {"sb": {}}}, "budget must be a mapping"),
        ({"sheetbooks": {"sb": {"budget": {}}}}, "max_sheets must be an integer"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": 1}}}}, "max_total_cells must be an integer"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": "nope", "max_total_cells": 1}}}}, "max_sheets must be an integer"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": "nope"}}}}, "max_total_cells must be an integer"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": 0, "max_total_cells": 1}}}}, "max_sheets must be"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 0}}}}, "max_total_cells must be"),
        (
            {"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": "nope"}}},
            "export_xlsx must be a mapping",
        ),
        (
            {"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {}}}},
            "export_xlsx.path must be a non-empty string",
        ),
        (
            {
                "sheetbooks": {
                    "sb": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {"path": "x.xlsx", "write_lock": "nope"}}
                }
            },
            "write_lock must be a bool",
        ),
        (
            {
                "sheetbooks": {
                    "sb": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {"path": "x.xlsx", "allow_formulas": "nope"}}
                }
            },
            "export_xlsx.allow_formulas must be a bool",
        ),
        (
            {"workbooks": {"same": {"path": "a.xlsx"}}, "csvs": {"same": {"path": "a.csv"}}},
            "ids must be unique",
        ),
        (
            {"workbooks": {"same": {"path": "a.xlsx"}}, "sheetbooks": {"same": {"budget": {"max_sheets": 1, "max_total_cells": 1}}}},
            "ids must be unique",
        ),
    ],
)
def test_load_workflow_config_from_mapping_resources_errors(resources_raw: Any, match: str) -> None:
    root = _base_root()
    root["workflow"]["resources"] = resources_raw
    with pytest.raises(ScalimWorkflowConfigError, match=match):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_allows_null_resource_groups() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"workbooks": None, "csvs": None, "sheetbooks": None}
    cfg = load_workflow_config_from_mapping(root)
    assert cfg.resources.workbooks == {}
    assert cfg.resources.csvs == {}
    assert cfg.resources.sheetbooks == {}


def test_load_workflow_config_from_mapping_validates_unknown_workbook_reference() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"workbooks": {"ok": {"path": "a.xlsx"}}}
    root["workflow"]["runs"][0]["writes"] = [{"workbook_sheet": {"workbook": "nope", "sheet": "S", "output": "detail"}}]
    with pytest.raises(ScalimWorkflowConfigError, match="Unknown workbook resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_validates_unknown_csv_reference() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"csvs": {"ok": {"path": "a.csv"}}}
    root["workflow"]["runs"][0]["writes"] = [{"csv_append": {"csv": "nope", "output": "detail"}}]
    with pytest.raises(ScalimWorkflowConfigError, match="Unknown csv resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_validates_unknown_sheetbook_reference() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"sheetbooks": {"ok": {"budget": {"max_sheets": 1, "max_total_cells": 1}}}}
    root["workflow"]["runs"][0]["writes"] = [{"sheetbook_sheet": {"sheetbook": "nope", "sheet": "S", "output": "detail"}}]
    with pytest.raises(ScalimWorkflowConfigError, match="Unknown sheetbook resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_accepts_sheetbook_append_surface() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 10}}}}
    root["workflow"]["runs"][0]["writes"] = [{"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "detail"}}]
    cfg = load_workflow_config_from_mapping(root)
    assert len(cfg.runs[0].writes) == 1
    assert type(cfg.runs[0].writes[0]).__name__ == "WorkflowWriteToSheetbookAppend"


def test_load_workflow_config_from_mapping_workbooks_raw_none_branch_is_exercised() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"workbooks": None}
    cfg = load_workflow_config_from_mapping(copy.deepcopy(root))
    assert cfg.resources.workbooks == {}


def test_load_workflow_config_from_mapping_csvs_raw_none_branch_is_exercised() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"csvs": None}
    cfg = load_workflow_config_from_mapping(copy.deepcopy(root))
    assert cfg.resources.csvs == {}


def test_load_workflow_config_from_mapping_sheetbooks_raw_none_branch_is_exercised() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"sheetbooks": None}
    cfg = load_workflow_config_from_mapping(copy.deepcopy(root))
    assert cfg.resources.sheetbooks == {}
