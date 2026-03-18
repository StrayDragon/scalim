import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from scalim.dsl.by_yaml.workflow import WorkflowConfigError, load_workflow_config, load_workflow_config_from_mapping


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

    with pytest.raises(WorkflowConfigError) as excinfo:
        _ = load_workflow_config(str(workflow_path))
    assert "Duplicate key" in str(excinfo.value)


def test_workflow_run_id_rejects_internal_prefix() -> None:
    root = _base_root()
    root["workflow"]["runs"][0]["id"] = "__wf__bad"
    with pytest.raises(WorkflowConfigError, match="reserved prefix"):
        _ = load_workflow_config_from_mapping(root)


@pytest.mark.parametrize(
    ("write_to_raw", "match"),
    [
        ("nope", "run.write_to must be a mapping"),
        ({1: {}}, "run.write_to keys must be non-empty strings"),
        ({"nope": {}}, "contains unknown keys"),
        ({}, "must contain exactly one of"),
        ({"workbook_sheet": {}, "csv_append": {}}, "must contain exactly one of"),
        ({"workbook_sheet": "nope"}, "must be a mapping"),
        ({"workbook_sheet": {1: "nope"}}, "keys must be non-empty strings"),
        ({"workbook_sheet": {"sheet": "S", "output": "o"}}, "workbook must be a non-empty string"),
        ({"workbook_sheet": {"workbook": "r", "output": "o"}}, "sheet must be a non-empty string"),
        ({"workbook_sheet": {"workbook": "r", "sheet": "S"}}, "output must be a non-empty string"),
        (
            {"workbook_sheet": {"workbook": "r", "sheet": "S", "output": "o", "on_conflict": "bad"}},
            "on_conflict must be one of",
        ),
        ({"workbook_append": {"sheet": "S", "output": "o"}}, "workbook must be a non-empty string"),
        ({"workbook_append": {"workbook": "r", "output": "o"}}, "sheet must be a non-empty string"),
        ({"workbook_append": {"workbook": "r", "sheet": "S"}}, "output must be a non-empty string"),
        (
            {"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "align_by": "bad"}},
            "align_by must be one of",
        ),
        (
            {"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "header_policy": "bad"}},
            "header_policy must be one of",
        ),
        (
            {"workbook_append": {"workbook": "r", "sheet": "S", "output": "o", "on_mismatch": "bad"}},
            "on_mismatch must be one of",
        ),
        ({"csv_append": {"output": "o"}}, "csv must be a non-empty string"),
        ({"csv_append": {"csv": "c"}}, "output must be a non-empty string"),
        ({"csv_append": {"csv": "c", "output": "o", "header_policy": "bad"}}, "header_policy must be one of"),
        ({"csv_append": {"csv": "c", "output": "o", "on_mismatch": "bad"}}, "on_mismatch must be one of"),
        ({"sheetbook_sheet": {"sheet": "S", "output": "o"}}, "sheetbook must be a non-empty string"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "output": "o"}}, "sheet name must be a non-empty string"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S"}}, "output must be a non-empty string"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "sheet": "Bad:Name", "output": "o"}}, "invalid characters"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "sheet": "x" * 32, "output": "o"}}, "too long"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S", "output": "o", "on_conflict": "bad"}}, "on_conflict must be one of"),
        ({"sheetbook_sheet": {"sheetbook": "sb", "sheet": "S", "output": "o"}}, "Unknown sheetbook resource id"),
        ({"sheetbook_append": {"sheet": "S", "output": "o"}}, "sheetbook must be a non-empty string"),
        ({"sheetbook_append": {"sheetbook": "sb", "sheet": "S"}}, "output must be a non-empty string"),
        ({"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "align_by": "bad"}}, "align_by must be one of"),
        ({"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "header_policy": "bad"}}, "header_policy must be one of"),
        ({"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "o", "on_mismatch": "bad"}}, "on_mismatch must be one of"),
    ],
)
def test_load_workflow_config_from_mapping_write_to_errors(write_to_raw: Any, match: str) -> None:
    root = _base_root()
    root["workflow"]["runs"][0]["write_to"] = write_to_raw
    with pytest.raises(WorkflowConfigError, match=match):
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
    with pytest.raises(WorkflowConfigError, match=match):
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
    root["workflow"]["runs"][0]["write_to"] = {"workbook_sheet": {"workbook": "nope", "sheet": "S", "output": "detail"}}
    with pytest.raises(WorkflowConfigError, match="Unknown workbook resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_validates_unknown_csv_reference() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"csvs": {"ok": {"path": "a.csv"}}}
    root["workflow"]["runs"][0]["write_to"] = {"csv_append": {"csv": "nope", "output": "detail"}}
    with pytest.raises(WorkflowConfigError, match="Unknown csv resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_validates_unknown_sheetbook_reference() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"sheetbooks": {"ok": {"budget": {"max_sheets": 1, "max_total_cells": 1}}}}
    root["workflow"]["runs"][0]["write_to"] = {"sheetbook_sheet": {"sheetbook": "nope", "sheet": "S", "output": "detail"}}
    with pytest.raises(WorkflowConfigError, match="Unknown sheetbook resource id"):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_accepts_sheetbook_append_surface() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 10}}}}
    root["workflow"]["runs"][0]["write_to"] = {"sheetbook_append": {"sheetbook": "sb", "sheet": "S", "output": "detail"}}
    cfg = load_workflow_config_from_mapping(root)
    write_to = cfg.runs[0].write_to
    assert write_to is not None
    assert type(write_to).__name__ == "WorkflowWriteToSheetbookAppend"


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
