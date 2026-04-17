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
        kind: xlsx_file
        path: ./a.xlsx
      report:
        kind: xlsx_file
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
        ({"books": {1: {"kind": "xlsx_file", "path": "a.xlsx"}}}, "workflow.resources.books keys must be non-empty strings"),
        ({"books": {"report": "nope"}}, "workflow.resources.books.report must be a mapping"),
        ({"books": {"report": {}}}, "workflow.resources.books.report.kind is required"),
        ({"books": {"report": {"kind": "nope"}}}, r"workflow.resources.books.report.kind=.*expected one of"),
        ({"books": {"report": {"kind": "xlsx_file"}}}, "path is required for kind=xlsx_file"),
        ({"books": {"report": {"kind": "xlsx_file", "path": 1}}}, "must be a non-empty string"),
        ({"books": {"report": {"kind": "xlsx_file", "path": "out", "nope": 1}}}, "has unknown keys"),
        ({"books": {"report": {"kind": "xlsx_file", "path": "a.xlsx"}}}, "output root directory"),
        (
            {"books": {"report": {"kind": "xlsx_file", "path": "out", "budget": {"max_sheets": 1, "max_total_cells": 1}}}},
            "budget is not allowed",
        ),
        ({"books": {"report": {"kind": "xlsx_file", "path": "out", "export_xlsx": {"path": "out2"}}}}, "export_xlsx is not allowed"),
        ({"books": {"report": {"kind": "xlsx_file", "path": "out", "allow_formulas": "nope"}}}, "allow_formulas must be a bool"),
        ({"books": {"report": {"kind": "xlsx_file", "path": "out", "write_lock": "nope"}}}, "write_lock was removed"),
        ({"books": {"mem": {"kind": "xlsx_memory", "budget": "nope"}}}, "budget must be a mapping"),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1, "nope": 1}}}},
            "budget has unknown keys",
        ),
        ({"books": {"mem": {"kind": "xlsx_memory", "budget": {}}}}, "max_sheets must be an integer"),
        ({"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1}}}}, "max_total_cells must be an integer"),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": "nope", "max_total_cells": 1}}}},
            "max_sheets must be an integer",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": "nope"}}}},
            "max_total_cells must be an integer",
        ),
        ({"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 0, "max_total_cells": 1}}}}, "max_sheets must be"),
        ({"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 0}}}}, "max_total_cells must be"),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "path": "a.xlsx"}}},
            "path is not allowed",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "allow_formulas": False}}},
            "allow_formulas is not allowed",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "write_lock": False}}},
            "write_lock was removed",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": "nope"}}},
            "export_xlsx must be a mapping",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "export_xlsx": {}}}},
            "export_xlsx.path is required",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "export_xlsx": {"path": "x.xlsx", "nope": 1},
                    }
                }
            },
            "export_xlsx has unknown keys",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "export_xlsx": {"path": "x.xlsx", "write_lock": "nope"},
                    }
                }
            },
            "write_lock was removed",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "export_xlsx": {"path": "out", "allow_formulas": "nope"},
                    }
                }
            },
            "export_xlsx.allow_formulas must be a bool",
        ),
        (
            {"books": {"mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "write_defaults": "nope"}}},
            "write_defaults must be a mapping",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "write_defaults": {"nope": 1},
                    }
                }
            },
            "write_defaults has unknown keys",
        ),
        (
            {
                "books": {
                    "mem": {"kind": "xlsx_memory", "budget": {"max_sheets": 1, "max_total_cells": 1}, "write_defaults": {"mode": "nope"}}
                }
            },
            r"write_defaults.mode=.*expected one of",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "write_defaults": {"align_by": "nope"},
                    }
                }
            },
            r"write_defaults.align_by=.*expected one of",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "write_defaults": {"header_policy": "nope"},
                    }
                }
            },
            r"write_defaults.header_policy=.*expected one of",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "write_defaults": {"on_mismatch": "nope"},
                    }
                }
            },
            r"write_defaults.on_mismatch=.*expected one of",
        ),
        (
            {
                "books": {
                    "mem": {
                        "kind": "xlsx_memory",
                        "budget": {"max_sheets": 1, "max_total_cells": 1},
                        "write_defaults": {"on_conflict": "nope"},
                    }
                }
            },
            r"write_defaults.on_conflict=.*expected one of",
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
    root["workflow"]["resources"] = {"books": {"report": {"kind": "xlsx_file", "path": tmp_path / "out"}}}
    cfg = load_workflow_config_from_mapping(root)
    assert cfg.resources.books["report"].path.endswith("out")


def test_load_workflow_config_from_mapping_xlsx_memory_budget_is_optional() -> None:
    root = _base_root()
    root["workflow"]["resources"] = {"books": {"mem": {"kind": "xlsx_memory"}}}
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
