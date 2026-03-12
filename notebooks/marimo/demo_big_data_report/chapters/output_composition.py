from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from notebooks.marimo.demo_big_data_report._derived_outputs_demo import DerivedOutputsDemoResult, run_derived_outputs_demo

from ._types import ChapterResult


def run_output_composition(tmp_path: Path) -> ChapterResult:
    workbook_path = tmp_path / "derived_outputs_demo.xlsx"
    result: DerivedOutputsDemoResult = run_derived_outputs_demo(str(workbook_path))
    passed = bool(result.passed)
    summary = "passed={} sheets={} rows={}".format(result.passed, len(result.sheet_names), result.total_rows)
    details: Dict[str, Any] = {"result": result}
    return ChapterResult(chapter_id="output_composition", passed=passed, summary=summary, details=details)
