"""Cells-native marimo notebook: ch090_workflow_shared_workbooks.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  resources_policy 装配、运行、四个 book 产物校验全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_shared_workbooks

        ## 回归点

        workflow 共享 workbooks：两个 demand 把明细写入同一 xlsx 资源（SHEET 覆写 /
        APPEND 追加），并覆盖 shapebook 引用链路（sheetbook 读上游 rows）。

        - `shared_report_sheet`：SHEET 模式 + OVERWRITE
        - `shared_report_append`：APPEND 模式 + align_by=HEADER + header ONCE + mismatch ERROR
        - `sheetbook_report_sheet/append`：经 workflow 内置 loader 的 sheetbook 链路

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置 + 工作副本（workflow.yaml + demand 拷贝到临时目录）
        2. 装配 `ResourcesPolicy`（4 个 book 写策略）+ `run_workflow`
        3. 产物解析（4 个 xlsx 的最新版本定位）
        4. 校验：sheet 行/表头计数（SHEET 覆写 vs APPEND 追加行数）
        5. 断言展开 → chapter_result

        Gate: `just examples`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from pathlib import Path

    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_shared_workbooks.yaml"
    _ = repo_root
    return Path, demo_dir, repo_root, workflow_yaml_path


@app.cell
def _(Path):
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional, Tuple

    from scalim.dsl.yaml_dsl import (
        BookResourcePolicy,
        BookWriteAlignBy,
        BookWriteHeaderPolicy,
        BookWriteMode,
        BookWriteOnConflict,
        BookWriteOnMismatch,
        BookWritePolicy,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        ResourcesPolicy,
        WorkflowRunOptions,
        run_workflow,
    )
    from scalim.shortcuts.resources import outputs as outputs_api
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, set_config
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        BookResourcePolicy,
        BookWriteAlignBy,
        BookWriteHeaderPolicy,
        BookWriteMode,
        BookWriteOnConflict,
        BookWriteOnMismatch,
        BookWritePolicy,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ECommerceConfig,
        List,
        Optional,
        Path,
        ResourcesPolicy,
        Tuple,
        WorkflowRunOptions,
        build_test_config_small,
        csv,
        make_chapter_result,
        outputs_api,
        render_checks,
        run_workflow,
        set_config,
        tempfile,
    )


@app.cell
def _(Any, Dict, List, Optional, Path, Tuple, csv, outputs_api):
    # 零件: CSV 表头计数 / xlsx sheet 计数 / book 产物定位
    def read_csv_header_and_count_rows(path: Path) -> Tuple[List[str], int]:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
            data_rows = sum(1 for _ in reader)
        return [str(x) for x in header], int(data_rows)

    def count_sheet_rows_and_header(workbook: Any, sheet_name: str) -> Tuple[Optional[List[str]], int]:
        if sheet_name not in workbook.sheetnames:
            return None, 0
        ws = workbook[sheet_name]
        it = ws.iter_rows(values_only=True)
        first = next(it, None)
        if first is None:
            return [], 0
        header = ["" if v is None else str(v) for v in first]
        rest_count = sum(1 for _ in it)
        return header, 1 + int(rest_count)

    def resolve_latest_book_artifact(out_root: Path, *, book_id: str) -> Tuple[Optional[Path], Dict[str, Any]]:
        try:
            latest = outputs_api.load_latest_outputs(out_root)
            path = latest.books.get(str(book_id))
            meta = {"run_id": latest.run_id, "books": sorted(latest.books.keys())}
            return path, meta
        except Exception as exc:  # noqa: BLE001
            return None, {"exc_type": type(exc).__name__, "message": str(exc)}

    return count_sheet_rows_and_header, read_csv_header_and_count_rows, resolve_latest_book_artifact


@app.cell
def _(Path, build_test_config_small, set_config, tempfile):
    import atexit
    import shutil

    cfg = build_test_config_small()
    set_config(cfg)
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders"])

    out_dir = Path(tempfile.mkdtemp(prefix="scalim-wf-wb-")).resolve()
    atexit.register(lambda: shutil.rmtree(out_dir, ignore_errors=True))
    print("out_dir:", out_dir)
    return allowed_modules, cfg, out_dir


@app.cell
def _(Path, out_dir, workflow_yaml_path):
    # 工作副本: workflow.yaml + demand 拷贝（child 目录相对引用）
    wf_copy = out_dir / "workflow.yaml"
    wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
    demand_dir = workflow_yaml_path.parent
    (out_dir / "workflow_demo_shared_workbooks_demand.yaml").write_text(
        (demand_dir / "workflow_demo_shared_workbooks_demand.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    print("wf_copy:", wf_copy)
    return wf_copy


@app.cell
def _(BookResourcePolicy, BookWriteAlignBy, BookWriteHeaderPolicy, BookWriteMode, BookWriteOnConflict, BookWriteOnMismatch, BookWritePolicy, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, ResourcesPolicy, WorkflowRunOptions, allowed_modules, out_dir, repo_root, run_workflow, wf_copy):
    # 装配: ResourcesPolicy(4 个 book 写策略) + run_workflow
    demand_options = DemandRunOptions(
        security=DemandRunSecurityOptions(
            allowed_modules=allowed_modules,
            allowed_yaml_roots=(str(repo_root),),
        ),
        template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
        runtime=DemandRunRuntimeOptions(batch_size=30),
    )
    resources_policy = ResourcesPolicy(
        books={
            "shared_report_sheet": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.SHEET,
                    on_conflict=BookWriteOnConflict.OVERWRITE,
                )
            ),
            "shared_report_append": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.APPEND,
                    align_by=BookWriteAlignBy.HEADER,
                    header_policy=BookWriteHeaderPolicy.ONCE,
                    on_mismatch=BookWriteOnMismatch.ERROR,
                )
            ),
            "sheetbook_report_sheet": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.SHEET,
                    on_conflict=BookWriteOnConflict.OVERWRITE,
                )
            ),
            "sheetbook_report_append": BookResourcePolicy(
                write=BookWritePolicy(
                    mode=BookWriteMode.APPEND,
                    align_by=BookWriteAlignBy.FIELD_ID,
                    header_policy=BookWriteHeaderPolicy.ONCE,
                    on_mismatch=BookWriteOnMismatch.ERROR,
                )
            ),
        }
    )
    wf_result = run_workflow(
        str(wf_copy),
        options=WorkflowRunOptions(
            demand=demand_options,
            path_aliases={"@": str(repo_root)},
            resources_policy=resources_policy,
        ),
    )

    errors = wf_result.errors()
    print("outcomes =", [o.run_id for o in wf_result.outcomes])
    print("errors   =", len(errors))
    return demand_options, errors, resources_policy, wf_result


@app.cell
def _(out_dir, resolve_latest_book_artifact):
    # 产物解析: 4 个 book 最新版本
    shared_report_sheet_root = out_dir / "out" / "shared_report_sheet"
    shared_report_append_root = out_dir / "out" / "shared_report_append"
    sheetbook_report_sheet_root = out_dir / "out" / "sheetbook_report_sheet"
    sheetbook_report_append_root = out_dir / "out" / "sheetbook_report_append"

    shared_report_sheet_xlsx, shared_sheet_meta = resolve_latest_book_artifact(
        shared_report_sheet_root, book_id="shared_report_sheet"
    )
    shared_report_append_xlsx, shared_append_meta = resolve_latest_book_artifact(
        shared_report_append_root, book_id="shared_report_append"
    )
    sheetbook_report_sheet_xlsx, sheetbook_sheet_meta = resolve_latest_book_artifact(
        sheetbook_report_sheet_root, book_id="sheetbook_report_sheet"
    )
    sheetbook_report_append_xlsx, sheetbook_append_meta = resolve_latest_book_artifact(
        sheetbook_report_append_root, book_id="sheetbook_report_append"
    )

    artifacts_ok = bool(
        shared_report_sheet_xlsx
        and shared_report_append_xlsx
        and sheetbook_report_sheet_xlsx
        and sheetbook_report_append_xlsx
        and shared_report_sheet_xlsx.exists()
        and shared_report_append_xlsx.exists()
        and sheetbook_report_sheet_xlsx.exists()
        and sheetbook_report_append_xlsx.exists()
    )
    print("artifacts_ok =", artifacts_ok)
    return (
        artifacts_ok,
        shared_append_meta,
        shared_sheet_meta,
        shared_report_append_root,
        shared_report_append_xlsx,
        shared_report_sheet_root,
        shared_report_sheet_xlsx,
        sheetbook_append_meta,
        sheetbook_report_append_root,
        sheetbook_report_append_xlsx,
        sheetbook_report_sheet_root,
        sheetbook_report_sheet_xlsx,
        sheetbook_sheet_meta,
    )


@app.cell
def _(Any, Dict, artifacts_ok, count_sheet_rows_and_header, shared_report_append_xlsx, shared_report_sheet_xlsx, sheetbook_report_append_xlsx, sheetbook_report_sheet_xlsx):
    # 校验: 4 个 xlsx 的 sheet 行/表头计数
    wb_ok = False
    sb_ok = False
    wb_checks: Dict[str, Any] = {}
    sb_checks: Dict[str, Any] = {}

    from openpyxl import load_workbook

    if artifacts_ok:
        wb_sheet = load_workbook(shared_report_sheet_xlsx, read_only=True, data_only=True)  # type: ignore[arg-type]
        try:
            wb_detail_header, wb_detail_rows = count_sheet_rows_and_header(wb_sheet, "Detail")
        finally:
            wb_sheet.close()

        wb_append = load_workbook(shared_report_append_xlsx, read_only=True, data_only=True)  # type: ignore[arg-type]
        try:
            wb_append_header, wb_append_rows = count_sheet_rows_and_header(wb_append, "DetailAppend")
        finally:
            wb_append.close()

        single_run_rows = int(wb_detail_rows) - 1 if wb_detail_rows else 0
        expected_append_rows = 1 + (2 * single_run_rows) if single_run_rows >= 0 else 0
        wb_ok = bool(
            wb_detail_header
            and wb_append_header
            and single_run_rows > 0
            and wb_detail_header == wb_append_header
            and wb_detail_rows == 1 + single_run_rows
            and wb_append_rows == expected_append_rows
        )
        wb_checks = {
            "header": wb_detail_header,
            "detail": {"rows_total": wb_detail_rows, "expected": 1 + single_run_rows},
            "detail_append": {"rows_total": wb_append_rows, "expected": expected_append_rows},
        }

        sb_sheet = load_workbook(sheetbook_report_sheet_xlsx, read_only=True, data_only=True)  # type: ignore[arg-type]
        try:
            sb_detail_header, sb_detail_rows = count_sheet_rows_and_header(sb_sheet, "Detail")
        finally:
            sb_sheet.close()

        sb_append = load_workbook(sheetbook_report_append_xlsx, read_only=True, data_only=True)  # type: ignore[arg-type]
        try:
            sb_append_header, sb_append_rows = count_sheet_rows_and_header(sb_append, "DetailAppend")
        finally:
            sb_append.close()

        sb_ok = bool(
            wb_ok
            and sb_detail_header == wb_detail_header
            and sb_append_header == wb_detail_header
            and sb_detail_rows == 1 + single_run_rows
            and sb_append_rows == expected_append_rows
        )
        sb_checks = {
            "header": sb_detail_header,
            "detail": {"rows_total": sb_detail_rows, "expected": 1 + single_run_rows},
            "detail_append": {"rows_total": sb_append_rows, "expected": expected_append_rows},
        }

    print("wb_ok =", wb_ok, "sb_ok =", sb_ok)
    return single_run_rows, sb_checks, sb_ok, wb_checks, wb_ok


@app.cell
def _(artifacts_ok, errors, render_checks, sb_ok, wb_ok):
    checks = {
        "无 errors": not errors,
        "4 个 xlsx 产物存在": artifacts_ok,
        "workbook SHEET/APPEND 行数正确": wb_ok,
        "sheetbook 链路一致": sb_ok,
    }
    render_checks(checks)
    return checks


@app.cell
def _(artifacts_ok, checks, errors, make_chapter_result, out_dir, sb_checks, sb_ok, shared_append_meta, shared_report_append_root, shared_report_append_xlsx, shared_report_sheet_root, shared_report_sheet_xlsx, shared_sheet_meta, sheetbook_append_meta, sheetbook_report_append_root, sheetbook_report_append_xlsx, sheetbook_report_sheet_root, sheetbook_report_sheet_xlsx, sheetbook_sheet_meta, wb_checks, wb_ok, wf_result, workflow_yaml_path):
    passed = bool(all(checks.values()))
    summary = "errors={} artifacts_ok={} wb_ok={} sheetbook_ok={}".format(
        len(errors),
        artifacts_ok,
        wb_ok,
        sb_ok,
    )
    if errors:
        summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "output_dir": str(out_dir),
            "workflow_yaml_path": str(workflow_yaml_path),
            "output_roots": {
                "shared_report_sheet": str(shared_report_sheet_root),
                "shared_report_append": str(shared_report_append_root),
                "sheetbook_report_sheet": str(sheetbook_report_sheet_root),
                "sheetbook_report_append": str(sheetbook_report_append_root),
            },
            "artifacts": {
                "shared_report_sheet_xlsx": str(shared_report_sheet_xlsx) if shared_report_sheet_xlsx else None,
                "shared_report_append_xlsx": str(shared_report_append_xlsx) if shared_report_append_xlsx else None,
                "sheetbook_report_sheet_xlsx": str(sheetbook_report_sheet_xlsx) if sheetbook_report_sheet_xlsx else None,
                "sheetbook_report_append_xlsx": str(sheetbook_report_append_xlsx) if sheetbook_report_append_xlsx else None,
            },
            "versioned_resolve": {
                "shared_report_sheet": shared_sheet_meta,
                "shared_report_append": shared_append_meta,
                "sheetbook_report_sheet": sheetbook_sheet_meta,
                "sheetbook_report_append": sheetbook_append_meta,
            },
            "workbook": wb_checks,
            "sheetbook": sb_checks,
            "errors": errors,
            "outcomes": wf_result.outcomes,
            "checks": {k: bool(v) for k, v in checks.items()},
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    mo.callout(
        mo.md("## {}: {}".format("✅ PASS" if chapter_result["passed"] else "❌ FAIL", chapter_result["summary"])),
        kind="success" if chapter_result["passed"] else "danger",
    )
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    table_rows = details_to_rows(chapter_result["details"])
    mo.ui.table(table_rows, selection=None) if table_rows else mo.md("(无详情)")
    return


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()