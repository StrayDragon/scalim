import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from scalim.dsl.yaml_dsl.workflow import ScalimWorkflowConfigError, load_workflow_config, load_workflow_config_from_mapping


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
    books:
      report:
        xlsx:
          path: ./out_a
      report:
        xlsx:
          path: ./out_b
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
    "writes_raw",
    [
        None,
        "nope",
        [],
        [{"workbook_sheet": {"workbook": "r", "sheet": "S", "output": "o"}}],
    ],
)
def test_load_workflow_config_from_mapping_writes_removed(writes_raw: Any) -> None:
    root = _base_root()
    root["workflow"]["runs"][0]["writes"] = writes_raw
    with pytest.raises(ScalimWorkflowConfigError) as excinfo:
        _ = load_workflow_config_from_mapping(root)
    assert "run.writes was removed" in str(excinfo.value)
    assert excinfo.value.path == "workflow.runs.0.writes"


@pytest.mark.parametrize(
    ("resources_raw", "match"),
    [
        ("nope", "workflow.resources must be a mapping"),
        ({1: {}}, "workflow.resources keys must be non-empty strings"),
        ({"": {}}, "workflow.resources keys must be non-empty strings"),
        ({"workbooks": {"report": {"path": "a.xlsx"}}}, "workflow.resources.workbooks was removed"),
        ({"csvs": {"merged": {"path": "a.csv"}}}, "workflow.resources.csvs was removed"),
        ({"sheetbooks": {"sb": {"budget": {"max_sheets": 1, "max_total_cells": 1}}}}, "workflow.resources.sheetbooks was removed"),
        ({"oops": {}}, "workflow.resources contains unknown keys"),
        ({"books": "nope"}, "workflow.resources.books must be a mapping"),
        ({"books": {1: {"xlsx": {"path": "out"}}}}, "workflow.resources.books keys must be non-empty strings"),
        ({"books": {"report": "nope"}}, "workflow.resources.books.report must be a mapping"),
        ({"books": {"report": {}}}, "must declare exactly one variant key"),
        ({"books": {"report": {"kind": "nope"}}}, "kind was removed"),
        ({"books": {"report": {"xlsx": {"path": ""}}}}, "xlsx.path must be a non-empty output root when provided"),
        ({"books": {"report": {"xlsx": {"path": 1}}}}, "must be a non-empty string"),
        ({"books": {"report": {"xlsx": {"path": "out"}, "nope": 1}}}, "has unknown keys"),
        ({"books": {"report": {"xlsx": {"path": "a.xlsx"}}}}, "output root directory"),
        (
            {"books": {"report": {"xlsx": {"path": "out", "budget": {"max_sheets": 1, "max_total_cells": 1}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        ({"books": {"report": {"xlsx": {"path": "out", "export_xlsx": {"path": "out2"}}}}}, "xlsx.export_xlsx is not allowed"),
        ({"books": {"report": {"xlsx": {"path": "out", "allow_formulas": "nope"}}}}, "allow_formulas must be a bool"),
        ({"books": {"report": {"xlsx": {"path": "out"}, "write_lock": "nope"}}}, "write_lock was removed"),
        ({"books": {"mem": {"xlsx": {"budget": "nope"}}}}, "xlsx.budget was removed from YAML authoring"),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1, "nope": 1}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        ({"books": {"mem": {"xlsx": {"budget": {}}}}}, "xlsx.budget was removed from YAML authoring"),
        ({"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1}}}}}, "xlsx.budget was removed from YAML authoring"),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": "nope", "max_total_cells": 1}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": "nope"}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 0, "max_total_cells": 1}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 0}}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "path": "a.xlsx"}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "allow_formulas": False}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "write_lock": False}}}},
            "xlsx.budget was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": "nope"}}}},
            "xlsx.export_xlsx is not allowed",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {}}}}},
            "xlsx.export_xlsx is not allowed",
        ),
        (
            {"books": {"mem": {"xlsx": {"budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {"path": "x.xlsx", "nope": 1}}}}},
            "xlsx.export_xlsx is not allowed",
        ),
        (
            {
                "books": {
                    "mem": {
                        "xlsx_memory": {
                            "export_xlsx": {"path": "x.xlsx", "write_lock": "nope"},
                        }
                    }
                }
            },
            "xlsx_memory with export_xlsx was removed",
        ),
        (
            {
                "books": {
                    "mem": {
                        "xlsx": {
                            "budget": {"max_sheets": 1, "max_total_cells": 1},
                            "export_xlsx": {"path": "out", "allow_formulas": "nope"},
                        }
                    }
                }
            },
            "xlsx.export_xlsx is not allowed",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": "nope"}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"nope": 1}}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"mode": "nope"}}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"align_by": "nope"}}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"header_policy": "nope"}}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"on_mismatch": "nope"}}}},
            "write_defaults was removed from YAML authoring",
        ),
        (
            {"books": {"mem": {"xlsx": {}, "write_defaults": {"on_conflict": "nope"}}}},
            "write_defaults was removed from YAML authoring",
        ),
    ],
)
def test_load_workflow_config_from_mapping_resources_errors(resources_raw: Any, match: str) -> None:
    root = _base_root()
    root["workflow"]["resources"] = resources_raw
    with pytest.raises(ScalimWorkflowConfigError, match=match):
        _ = load_workflow_config_from_mapping(root)


def test_load_workflow_config_from_mapping_books_path_accepts_pathlike(tmp_path: Path) -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"books": {"report": {"xlsx": {"path": tmp_path / "out"}}}}
    cfg = load_workflow_config_from_mapping(root)
    assert cfg.resources.books["report"].path.endswith("out")


def test_load_workflow_config_from_mapping_xlsx_memory_budget_is_optional() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"books": {"mem": {"xlsx": {}}}}
    cfg = load_workflow_config_from_mapping(root)
    assert cfg.resources.books["mem"].kind == "xlsx_memory"
    assert cfg.resources.books["mem"].budget is None


def test_load_workflow_config_from_mapping_allows_null_resource_groups() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"books": None}
    cfg = load_workflow_config_from_mapping(root)
    assert cfg.resources.books == {}


def test_load_workflow_config_from_mapping_resources_raw_none_branch_is_exercised() -> None:
    root = _base_root()
    root["workflow"]["resources"] = None
    cfg = load_workflow_config_from_mapping(copy.deepcopy(root))
    assert cfg.resources.books == {}


def test_load_workflow_config_from_mapping_books_raw_none_branch_is_exercised() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"books": None}
    cfg = load_workflow_config_from_mapping(copy.deepcopy(root))
    assert cfg.resources.books == {}
