from pathlib import Path
from typing import Any, Dict

from ..derived_set_aggregations_demo import DerivedSetAggregationsDemoResult, run_derived_set_aggregations_demo
from ._types import ChapterResult


def run_derived_set_aggregations(tmp_path: Path) -> ChapterResult:
    workbook_path = tmp_path / "derived_set_aggregations_demo.xlsx"
    result: DerivedSetAggregationsDemoResult = run_derived_set_aggregations_demo(str(workbook_path))
    passed = bool(result.passed)
    summary = "passed={} sheets={} detail_rows={}".format(result.passed, len(result.sheet_names), len(result.detail_rows))
    details: Dict[str, Any] = {"result": result}
    return ChapterResult(chapter_id="derived_set_aggregations", passed=passed, summary=summary, details=details)
