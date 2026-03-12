from __future__ import annotations

import os
import tempfile
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_csv import CSVSink, ColumnCSVSink
from scalim.sinks.sink_memory import InMemoryColumnSink, InMemoryRowSink

from notebooks.marimo.demo_big_data_report._loaders import ECommerceConfig, set_config
from notebooks.marimo.demo_big_data_report._shared import build_ecommerce_model
from notebooks.marimo.demo_big_data_report._verification import (
    VerificationResult,
    compare_csv_files,
    export_to_csv,
    python_build_order_report,
    verify_scalim_output,
)

from ._types import ChapterResult


def _run_engine_to_rows(cfg: ECommerceConfig, targets: Sequence[str], *, batch_size: int) -> List[Dict[str, Any]]:
    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    plan = PlanBuilder(demand).build(targets=list(targets))
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
    with InMemoryRowSink() as sink:
        engine.run(main_rows=None, sink=sink)
        return sink.get_data()


def _run_engine_to_columns(cfg: ECommerceConfig, targets: Sequence[str], *, batch_size: int) -> List[Dict[str, Any]]:
    set_config(cfg)
    demand = build_ecommerce_model(cfg)
    plan = PlanBuilder(demand).build(targets=list(targets))
    engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
    with InMemoryColumnSink(field_names=list(targets)) as sink:
        engine.run(main_rows=None, sink=sink)
        return sink.get_rows()


def _optional_pandas_rows(
    results: List[Dict[str, Any]], *, targets: Sequence[str]
) -> Tuple[bool, Optional[VerificationResult], Optional[VerificationResult]]:
    try:
        import pandas as pd  # noqa: PLC0415
    except ImportError:
        return False, None, None

    df = pd.DataFrame(results)
    df = df[list(targets)]
    rows = df.to_dict("records")
    vr = verify_scalim_output(rows, fields_to_check=list(targets))
    return True, vr, vr


def run_sinks(cfg: ECommerceConfig, *, targets: Sequence[str], batch_size: int = 50) -> ChapterResult:
    """多种输出方式 + 文件对拍."""
    targets_list = list(targets)

    start = time.time()
    row_results = _run_engine_to_rows(cfg, targets_list, batch_size=batch_size)
    col_results = _run_engine_to_columns(cfg, targets_list, batch_size=batch_size)
    elapsed_engine = time.time() - start

    vr_row = verify_scalim_output(row_results, fields_to_check=targets_list)
    vr_col = verify_scalim_output(col_results, fields_to_check=targets_list)

    # `CSV`: 输出文件与纯 `Python` 对照组做对拍
    py_results = python_build_order_report(targets_list)
    with tempfile.TemporaryDirectory() as tmpdir:
        scalim_csv = os.path.join(tmpdir, "scalim.csv")
        python_csv = os.path.join(tmpdir, "python.csv")
        export_to_csv(col_results, scalim_csv, targets_list)
        export_to_csv(py_results, python_csv, targets_list)
        csv_matched, csv_diff = compare_csv_files(scalim_csv, python_csv)

        # 额外: 真实 `CSVSink`/`ColumnCSVSink` 输出(仅校验能跑通 + 行数一致)
        csv_row_path = os.path.join(tmpdir, "row_sink.csv")
        csv_col_path = os.path.join(tmpdir, "col_sink.csv")

        set_config(cfg)
        demand = build_ecommerce_model(cfg)
        plan = PlanBuilder(demand).build(targets=targets_list)
        engine = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
        with CSVSink(csv_row_path, field_names=targets_list) as sink_row:
            _ = sink_row
            engine.run(main_rows=None, sink=sink_row)

        engine2 = ScalimEngine(demand=demand, plan=plan, batch_size=int(batch_size))
        with ColumnCSVSink(csv_col_path, field_names=targets_list) as sink_col:
            _ = sink_col
            engine2.run(main_rows=None, sink=sink_col)

        with open(csv_row_path, encoding="utf-8") as f:
            row_lines = sum(1 for _ in f) - 1
        with open(csv_col_path, encoding="utf-8") as f:
            col_lines = sum(1 for _ in f) - 1

    pandas_available, vr_pd_row, vr_pd_col = _optional_pandas_rows(col_results, targets=targets_list)

    passed = bool(vr_row.passed and vr_col.passed and csv_matched and row_lines == len(col_results) and col_lines == len(col_results))
    if pandas_available and vr_pd_row and vr_pd_col:
        passed = passed and vr_pd_row.passed and vr_pd_col.passed

    summary = "engine_elapsed={:.3f}s rows={} verify_row={} verify_col={} csv_match={} csv_sinks_rows={}/{}".format(
        elapsed_engine,
        len(col_results),
        vr_row.passed,
        vr_col.passed,
        csv_matched,
        row_lines,
        col_lines,
    )
    if not csv_matched:
        summary = summary + "\n" + (csv_diff or "(csv diff unavailable)")

    details: Dict[str, Any] = {
        "targets": targets_list,
        "rows": len(col_results),
        "engine_elapsed_seconds": elapsed_engine,
        "verify_row": vr_row,
        "verify_col": vr_col,
        "csv_matched": csv_matched,
        "csv_diff": csv_diff,
        "pandas_available": pandas_available,
        "verify_pandas_row": vr_pd_row,
        "verify_pandas_col": vr_pd_col,
    }
    return ChapterResult(chapter_id="sinks", passed=passed, summary=summary, details=details)
