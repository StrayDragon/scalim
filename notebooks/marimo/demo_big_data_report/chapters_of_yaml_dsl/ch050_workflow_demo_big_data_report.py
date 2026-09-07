"""Cells-native marimo notebook: ch050_workflow_demo_big_data_report.

迁移对照:
  Before: 模块级 run_workflow_demo_big_data_report() + _run_in_dir 闭包持全部逻辑
  After:  工作副本准备/run/chunk 观察/三路验证全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_demo_big_data_report

        ## 背景

        workflow fixture 能证明“能跑”，但真实使用通常还会涉及：
        - resources（sheetbook/csv 等资源托管）
        - writes（把上游 output 写入到资源）
        - depends_on（显式 DAG）
        - workflow 内置 `loader`（从共享 `sheetbook` 读取上游 rows）
        - cache_pool（workflow-scope cache，共享 `preload_forever`）

        ## 需求方提问（自然语言）

        业务方：能给一个更像生产的 workflow demo 吗？我想在 PR 里改 YAML 后能稳定对拍。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置 + 零件（KeysChunkObserver/Hook、CSV 读取、纯 Python 对照组）
        2. 工作副本（拷贝 workflow + demand YAML 到 out_dir，产物落 `.tmp/artifacts/`）
        3. `run_workflow`（cache_pool + lookup_chunking + 组件注入）
        4. 输出定位 + 明细对拍（verify_scalim_output_csv）
        5. metrics 对照组 + chunk oracle + 产物断言
        6. 汇总 chapter_result

        ## 对拍点（deterministic）

        - workflow YAML：`chapters_of_yaml_dsl/declared_yaml_dsl/workflow_demo_big_data_report.yaml`
        - 断言：
          - `depends_on` + `scalim.workflow.loaders.sheetbook_sheet_rows` 链路可跑通（detail → metrics）
          - 产物存在：`detail.csv` / `metrics.csv` / `report.xlsx`
          - `cache_pool` 生效：`preload_forever` 共享 loader 仅调用 1 次
          - 明细 CSV 与纯 Python 对照组一致：`verify_scalim_output_csv`
        - Gate：`just examples`
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
    workflow_yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_demo_big_data_report.yaml"
    _ = repo_root
    return Path, demo_dir, repo_root, workflow_yaml_path


@app.cell(hide_code=True)
def _(mo, workflow_yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow YAML")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_path, max_lines=160)))
    return (excerpt_head,)


@app.cell
def _(Path):
    import csv
    import os
    import shutil
    from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

    from scalim.dsl.yaml_dsl import (
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        LookupChunking,
        WorkflowRunOptions,
        run_workflow,
    )
    from scalim.dsl.yaml_dsl.workflow_types import WorkflowCachePoolPreloadForeverShared, WorkflowExecutionOptions, WorkflowRuntimeOptions
    from scalim.events import Event, EventType
    from scalim.hooks import BaseHook
    from scalim.ob.observer import Observer
    from scalim.shortcuts.resources import outputs as outputs_api
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import (
        ECommerceConfig,
        get_workflow_preload_counter_calls,
        reset_workflow_preload_counter_calls,
    )
    from scalim_misc.demo_big_data_report.shared import TARGET_FIELDS_FULL
    from scalim_misc.demo_big_data_report.verification import VerificationResult, verify_scalim_output_csv
    from scalim_misc.examples.oracle import diff_first_mismatch, stable_sort_rows
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        BaseHook,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ECommerceConfig,
        Event,
        EventType,
        List,
        LookupChunking,
        Mapping,
        Observer,
        Optional,
        Path,
        Sequence,
        Set,
        TARGET_FIELDS_FULL,
        VerificationResult,
        WorkflowCachePoolPreloadForeverShared,
        WorkflowExecutionOptions,
        WorkflowRunOptions,
        WorkflowRuntimeOptions,
        build_test_config_small,
        csv,
        diff_first_mismatch,
        get_workflow_preload_counter_calls,
        make_chapter_result,
        os,
        outputs_api,
        render_checks,
        reset_workflow_preload_counter_calls,
        run_workflow,
        shutil,
        stable_sort_rows,
        verify_scalim_output_csv,
    )


@app.cell
def _(build_test_config_small, reset_workflow_preload_counter_calls, set_config):
    # 需要 set_config —— 由本 cell 引入
    from scalim_misc.demo_big_data_report.loaders import set_config

    cfg = build_test_config_small()
    set_config(cfg)
    reset_workflow_preload_counter_calls()
    LOOKUP_CHUNK = 5
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders", "scalim.workflow.loaders"])
    print("customer_count =", cfg.customer_count, "product_count =", cfg.product_count)
    return LOOKUP_CHUNK, allowed_modules, cfg, set_config


@app.cell
def _(BaseHook, Dict, Event, EventType, List, Observer, Optional, Path, Set):
    from decimal import Decimal

    # 零件: 观察 customers/products 的 lookup 分块调用
    class KeysChunkObserver(Observer):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
            self.by_source: Dict[str, List[Optional[int]]] = {"customers": [], "products": []}
            self.miss_offsets: Dict[str, List[int]] = {"customers": [], "products": []}
            self.hit_offsets: Dict[str, List[Optional[int]]] = {"customers": [], "products": []}
            self.unchunked_misses: Dict[str, int] = {"customers": 0, "products": 0}

        def on_event(self, event: Event) -> None:
            if event.event_type is not EventType.LOADER_CALL:
                return
            payload = event.payload
            name = str(getattr(payload, "loader_name", "") or "")
            if name not in self.by_source:
                return
            offset = getattr(payload, "chunk_offset", None)
            parsed = None if offset is None else int(offset)
            self.by_source[name].append(parsed)
            cache_status = str(getattr(payload, "cache_status", "") or "")
            if cache_status == "hit":
                self.hit_offsets[name].append(parsed)
                return
            if parsed is None:
                self.unchunked_misses[name] += 1
                return
            self.miss_offsets[name].append(parsed)

    # 零件: Hook 视角的同一调用计数
    class KeysChunkHook(BaseHook):
        def __init__(self) -> None:
            self.event_types: Optional[Set[EventType]] = {EventType.LOADER_CALL}
            self.by_source: Dict[str, int] = {"customers": 0, "products": 0}

        def on_loader_call(self, event: Event) -> None:
            payload = event.payload
            name = str(getattr(payload, "loader_name", "") or "")
            if name in self.by_source:
                self.by_source[name] += 1

    # 零件: CSV 读取
    def read_csv_rows(path: Path) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if not row:
                    continue
                rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
        return rows

    # 零件: 纯 Python 对照组(按区域聚合 metrics)
    def build_expected_metrics_rows(*, detail_rows: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
        by_region: Dict[str, Dict[str, Any]] = {}
        for row in detail_rows:
            region = str(row.get("region_name_display") or "")
            acc = by_region.setdefault(region, {"region_name_display": region, "order_cnt": 0, "sum_order_amount": Decimal("0")})
            acc["order_cnt"] = int(acc["order_cnt"]) + 1
            try:
                amount = Decimal(str(row.get("order_amount") or "0"))
            except Exception:  # noqa: BLE001
                amount = Decimal("0")
            acc["sum_order_amount"] = acc["sum_order_amount"] + amount

        rows: List[Dict[str, str]] = []
        for region, acc in by_region.items():
            rows.append(
                {
                    "region_name_display": region,
                    "order_cnt": str(acc["order_cnt"]),
                    "sum_order_amount": str(acc["sum_order_amount"]),
                }
            )
        return rows

    return Decimal, KeysChunkHook, KeysChunkObserver, build_expected_metrics_rows, read_csv_rows


@app.cell
def _(Path, repo_root, shutil, workflow_yaml_path):
    # 工作副本: 产物落 .tmp/artifacts/(可交互查看),clean 后重写 workflow + demand
    out_dir = Path(__file__).resolve().parents[4] / ".tmp" / "artifacts" / "demo_big_data_report" / "workflow_demo_big_data_report"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_root = out_dir / "out"

    shutil.rmtree(str(out_root), ignore_errors=True)
    for filename in ("workflow.yaml",):
        try:
            (out_dir / filename).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    wf_copy = out_dir / "workflow.yaml"
    wf_copy.write_text(workflow_yaml_path.read_text(encoding="utf-8"), encoding="utf-8")

    demand_dir = workflow_yaml_path.parent
    for demand_filename in (
        "workflow_demo_big_data_report_detail_demand.yaml",
        "workflow_demo_big_data_report_metrics_demand.yaml",
    ):
        (out_dir / demand_filename).write_text((demand_dir / demand_filename).read_text(encoding="utf-8"), encoding="utf-8")

    print("out_dir :", out_dir)
    print("out_root:", out_root)
    print("workflow copy:", wf_copy)
    return out_dir, out_root, wf_copy


@app.cell
def _(
    LOOKUP_CHUNK,
    KeysChunkHook,
    KeysChunkObserver,
    LookupChunking,
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    WorkflowCachePoolPreloadForeverShared,
    WorkflowExecutionOptions,
    WorkflowRunOptions,
    WorkflowRuntimeOptions,
    allowed_modules,
    os,
    repo_root,
    run_workflow,
    wf_copy,
):
    # 运行 workflow(需 cwd=out_dir 解析相对引用;finally 恢复)
    prev_cwd = os.getcwd()
    os.chdir(str(wf_copy.parent))
    try:
        workflow_runtime_options = WorkflowRuntimeOptions(
            execution=WorkflowExecutionOptions(max_concurrency=2, failure_policy="all_fail"),
            cache_pool=WorkflowCachePoolPreloadForeverShared(max_entries=16),
        )
        observer = KeysChunkObserver()
        hook = KeysChunkHook()
        demand_options = DemandRunOptions(
            security=DemandRunSecurityOptions(
                allowed_modules=allowed_modules,
                allowed_yaml_roots=(str(repo_root),),
            ),
            template=DemandRunTemplateOptions(init_vars={"order_ids": []}),
            runtime=DemandRunRuntimeOptions(
                batch_size=30,
                lookup_chunking={
                    "customers": LookupChunking.sized(LOOKUP_CHUNK),
                    "products": LookupChunking.sized(LOOKUP_CHUNK),
                },
                components=[observer, hook],
            ),
        )
        result = run_workflow(
            str(wf_copy),
            options=WorkflowRunOptions(
                demand=demand_options,
                runtime=workflow_runtime_options,
                path_aliases={"@": str(repo_root)},
            ),
        )
    finally:
        os.chdir(prev_cwd)

    errors = result.errors()
    print("outcomes      =", [o.run_id for o in result.outcomes])
    print("errors        =", len(errors))
    print("customers 分块=", observer.by_source["customers"])
    print("products 分块 =", observer.by_source["products"])
    return errors, hook, observer, result


@app.cell
def _(
    TARGET_FIELDS_FULL,
    VerificationResult,
    get_workflow_preload_counter_calls,
    hook,
    observer,
    outputs_api,
    out_root,
    result,
    verify_scalim_output_csv,
):
    # 输出定位 + 明细对拍
    preload_calls = get_workflow_preload_counter_calls()
    latest = outputs_api.load_latest_outputs(out_root)
    version_id = str(latest.run_id)
    any_artifact = None
    if latest.files:
        any_artifact = next(iter(latest.files.values()))
    elif latest.books:
        any_artifact = next(iter(latest.books.values()))
    version_dir = any_artifact.parent.parent if any_artifact is not None else None

    missing = out_root / "__missing__"
    detail_csv = latest.files.get("detail_csv") or missing
    metrics_csv = latest.files.get("metrics_csv") or missing
    report_xlsx = latest.books.get("report") or missing

    verification: VerificationResult
    if detail_csv.exists():
        verification = verify_scalim_output_csv(detail_csv, fields_to_check=TARGET_FIELDS_FULL)
    else:
        verification = VerificationResult(
            passed=False,
            total_rows=0,
            checked_rows=0,
            mismatches=[],
            summary="Missing detail_csv.csv",
        )

    print("version_id   =", version_id)
    print("detail_csv   =", detail_csv)
    print("metrics_csv  =", metrics_csv)
    print("report_xlsx  =", report_xlsx)
    print("verify       =", verification.passed)

    return (
        detail_csv,
        latest,
        metrics_csv,
        missing,
        preload_calls,
        report_xlsx,
        verification,
        version_dir,
        version_id,
    )


@app.cell
def _(build_expected_metrics_rows, detail_csv, diff_first_mismatch, metrics_csv, read_csv_rows, stable_sort_rows):
    # metrics 对照组(detail 行 → 纯 Python 聚合 → 与 metrics.csv 对拍)
    metrics_ok = False
    metrics_summary = "missing metrics.csv"
    if detail_csv.exists() and metrics_csv.exists():
        detail_rows = read_csv_rows(detail_csv)
        actual_metrics = stable_sort_rows(read_csv_rows(metrics_csv), by=("region_name_display",))
        expected_metrics = stable_sort_rows(build_expected_metrics_rows(detail_rows=detail_rows), by=("region_name_display",))
        metrics_ok, metrics_summary = diff_first_mismatch(
            actual_metrics,
            expected_metrics,
            fields=("region_name_display", "order_cnt", "sum_order_amount"),
        )
    print("metrics_ok =", metrics_ok, "|", metrics_summary)
    return metrics_ok, metrics_summary


@app.cell
def _(
    LOOKUP_CHUNK, cfg, detail_csv, errors, hook, metrics_csv, metrics_ok, observer, preload_calls, render_checks, report_xlsx, verification
):
    # 断言展开(chunk oracle / 产物 / preload)
    artifacts_ok = bool(detail_csv.exists() and metrics_csv.exists() and report_xlsx.exists())
    customer_offsets = list(range(0, int(cfg.customer_count), LOOKUP_CHUNK))
    product_offsets = list(range(0, int(cfg.product_count), LOOKUP_CHUNK))
    customer_miss_ok = observer.miss_offsets["customers"] == customer_offsets
    product_miss_ok = set(observer.miss_offsets["products"]) == set(product_offsets)
    no_unchunked_miss = observer.unchunked_misses["customers"] == 0 and observer.unchunked_misses["products"] == 0
    hits_unchunked = all(offset is None for offsets in observer.hit_offsets.values() for offset in offsets)
    hook_ok = bool(
        hook.by_source["customers"] == len(observer.by_source["customers"])
        and hook.by_source["products"] == len(observer.by_source["products"])
    )
    chunk_ok = bool(customer_miss_ok and product_miss_ok and no_unchunked_miss and hits_unchunked and hook_ok)

    checks = {
        "无 errors": not errors,
        "preload 仅 1 次": preload_calls == 1,
        "产物齐全": artifacts_ok,
        "明细 CSV 对照组一致": verification.passed,
        "metrics 对照组一致": metrics_ok,
        "lookup chunk oracle": chunk_ok,
    }
    render_checks(checks)
    return artifacts_ok, checks, chunk_ok


@app.cell
def _(
    artifacts_ok,
    checks,
    chunk_ok,
    detail_csv,
    errors,
    hook,
    make_chapter_result,
    metrics_csv,
    metrics_ok,
    metrics_summary,
    observer,
    out_root,
    preload_calls,
    report_xlsx,
    result,
    verification,
    version_dir,
    version_id,
):
    passed = bool(all(checks.values()))
    summary = "errors={} preload_calls={} artifacts_ok={} verify={} customers_chunks={} products_chunks={}".format(
        len(errors),
        preload_calls,
        artifacts_ok,
        verification.passed,
        observer.by_source["customers"],
        observer.by_source["products"],
    )
    if errors:
        summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)
    if not verification.passed:
        summary = summary + "\n" + verification.summary
    if not metrics_ok:
        summary = summary + "\nmetrics: " + metrics_summary
    if not chunk_ok:
        summary = summary + "\nlookup chunk oracle failed hook={} miss={} hits={} unchunked_miss={}".format(
            hook.by_source,
            observer.miss_offsets,
            observer.hit_offsets,
            observer.unchunked_misses,
        )

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "output_dir": str(out_root),
            "out_root": str(out_root),
            "version_id": version_id,
            "version_dir": str(version_dir) if version_dir is not None else None,
            "detail_csv": str(detail_csv),
            "metrics_csv": str(metrics_csv),
            "report_xlsx": str(report_xlsx),
            "verification": verification,
            "metrics": {"passed": metrics_ok, "summary": metrics_summary},
            "errors": errors,
            "outcomes": result.outcomes,
            "customers_chunk_offsets": list(observer.by_source["customers"]),
            "products_chunk_offsets": list(observer.by_source["products"]),
            "chunk_hook_calls": dict(hook.by_source),
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
