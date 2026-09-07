"""Cells-native marimo notebook: ch070_yaml_dsl_output_failure_policy.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  零件/三个 failure-policy 场景/断言全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_output_failure_policy

        ## 回归点

        输出失败策略的三种确定性场景（次输出 workbook 写入被目录冲突触发失败）：
        1. `primary_only` + 脱敏错误信息（error_message 需被 sha256 摘要替身）
        2. `primary_only` + 完整错误信息（`DemandDiagnosticsPolicy(include_full_error_message=True)`）
        3. `all_fail` 预期整体抛错

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 零件：CSV 读取 / stats 汇总 / hex 校验 / 写入冲突注入
        2. 场景 A（redacted）→ 校验 primary 成功 + secondary disabled + 错误脱敏
        3. 场景 B（full）→ 校验错误信息非脱敏
        4. 场景 C（all_fail）→ 预期抛错
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
    support_dir = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support"
    allowed_yaml_roots = (str(support_dir.parent),)
    yaml_redacted_path = support_dir / "support_output_failure_primary_only_redacted.yaml"
    yaml_full_path = support_dir / "support_output_failure_primary_only_full.yaml"
    yaml_all_fail_path = support_dir / "support_output_failure_all_fail.yaml"
    _ = repo_root
    return (
        Path,
        allowed_yaml_roots,
        demo_dir,
        support_dir,
        yaml_all_fail_path,
        yaml_full_path,
        yaml_redacted_path,
    )


@app.cell
def _(Path):
    import csv
    import logging
    import tempfile
    from typing import Any, Dict, List, Optional, Sequence

    from scalim.dsl.yaml_dsl import (
        DemandDiagnosticsPolicy,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
    )
    from scalim.dsl.yaml_dsl import compile as compile_yaml
    from scalim.execution.output_composition import OutputTargetStats
    from scalim.execution import run_ir
    from scalim.execution import versioned_outputs
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandDiagnosticsPolicy,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        List,
        Optional,
        OutputTargetStats,
        Path,
        Sequence,
        compile_yaml,
        csv,
        logging,
        make_chapter_result,
        render_checks,
        run_ir,
        tempfile,
        versioned_outputs,
    )


@app.cell
def _(Any, Dict, List, Optional, OutputTargetStats, Path, Sequence, csv, logging):
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

    # 零件: 64 位 hex 校验
    def is_hex_64(value: Optional[str]) -> bool:
        if not value:
            return False
        v = str(value).strip().lower()
        if len(v) != 64:
            return False
        for ch in v:
            if ch not in "0123456789abcdef":
                return False
        return True

    # 零件: stats 汇总
    def stats_by_id(stats: Optional[Sequence[OutputTargetStats]]) -> Dict[str, OutputTargetStats]:
        by_id: Dict[str, OutputTargetStats] = {}
        for s in stats or ():
            by_id[str(s.target_id)] = s
        return by_id

    def summarize_stats(stats: Optional[Sequence[OutputTargetStats]]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for s in stats or ():
            rows.append(
                {
                    "target_id": str(s.target_id),
                    "disabled": bool(s.disabled),
                    "row_count": int(s.row_count),
                    "error_count": int(s.error_count),
                    "error_type": str(s.error_type or ""),
                    "error_message": str(s.error_message or ""),
                    "error_message_hash": str(s.error_message_hash or ""),
                    "output_path": str(s.output_path or ""),
                    "sheet_name": str(s.sheet_name or ""),
                }
            )
        return rows

    # 零件: 在“应为文件”的路径上预先创建同名目录,构造确定性写入失败
    def inject_output_dir_conflict_for_target(*, output_path: str) -> Path:
        p = Path(str(output_path))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.mkdir(parents=False, exist_ok=True)
        return p

    _ = logging
    return (
        inject_output_dir_conflict_for_target,
        is_hex_64,
        read_csv_rows,
        stats_by_id,
        summarize_stats,
    )


@app.cell
def _(Path, logging, tempfile):
    import atexit
    import shutil

    # 静音 excel sink 的 ERROR 堆栈日志(避免 just examples 输出噪音)
    sink_logger = logging.getLogger("scalim.sinks.sink_excel")
    sink_logger.setLevel(logging.CRITICAL)

    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])

    tmp = Path(tempfile.mkdtemp(prefix="scalim-output-failure-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root_secondary = tmp / "out_secondary_workbook"
    print("tmp dir:", tmp)
    return ALLOWED_MODULES, out_root_secondary, sink_logger, tmp


@app.cell
def _(
    ALLOWED_MODULES,
    Dict,
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    Path,
    allowed_yaml_roots,
    compile_yaml,
    inject_output_dir_conflict_for_target,
    is_hex_64,
    read_csv_rows,
    run_ir,
    stats_by_id,
    tmp,
    versioned_outputs,
    yaml_redacted_path,
):
    # 场景 A: primary_only + 脱敏错误信息
    out_root_detail_redacted = tmp / "out_detail_redacted"
    init_vars_redacted: Dict[str, object] = {
        "out_path_detail": str(out_root_detail_redacted),
        "out_path_secondary_workbook": str(tmp / "out_secondary_workbook"),
    }

    redacted_compilation = compile_yaml(
        str(yaml_redacted_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(
                allowed_modules=ALLOWED_MODULES,
                allowed_yaml_roots=allowed_yaml_roots,
            ),
            template=DemandRunTemplateOptions(init_vars=init_vars_redacted),
            runtime=DemandRunRuntimeOptions(
                demand_failure_policy="primary_only",
                batch_size=2,
            ),
        ),
    )
    redacted_spec = redacted_compilation.request.output_composition
    secondary_output_path_a = None
    for t_a in redacted_spec.targets if redacted_spec is not None else ():
        if str(t_a.target_id) == "secondary_debug_workbook":
            secondary_output_path_a = str(t_a.output.path)
            break
    if not secondary_output_path_a:
        raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
    _ = inject_output_dir_conflict_for_target(output_path=str(secondary_output_path_a))
    redacted_core = run_ir(redacted_compilation.demand_ir, redacted_compilation.request)

    redacted_output_path = Path(str((redacted_core.outputs or {}).get("detail") or redacted_core.output_path or ""))
    redacted_rows = read_csv_rows(redacted_output_path) if redacted_output_path.exists() else []
    redacted_stats = stats_by_id(redacted_core.output_target_stats)

    return (
        ALLOWED_MODULES,
        out_root_detail_redacted,
        redacted_compilation,
        redacted_core,
        redacted_output_path,
        redacted_rows,
        redacted_stats,
    )


@app.cell
def _(
    ALLOWED_MODULES,
    DemandDiagnosticsPolicy,
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    Dict,
    Path,
    allowed_yaml_roots,
    compile_yaml,
    inject_output_dir_conflict_for_target,
    read_csv_rows,
    run_ir,
    stats_by_id,
    tmp,
    yaml_full_path,
):
    # 场景 B: primary_only + 完整错误信息
    out_root_detail_full = tmp / "out_detail_full"
    init_vars_full: Dict[str, object] = {
        "out_path_detail": str(out_root_detail_full),
        "out_path_secondary_workbook": str(tmp / "out_secondary_workbook"),
    }

    full_compilation = compile_yaml(
        str(yaml_full_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(
                allowed_modules=ALLOWED_MODULES,
                allowed_yaml_roots=allowed_yaml_roots,
            ),
            template=DemandRunTemplateOptions(init_vars=init_vars_full),
            runtime=DemandRunRuntimeOptions(
                demand_failure_policy="primary_only",
                demand_diagnostics=DemandDiagnosticsPolicy(include_full_error_message=True),
                batch_size=2,
            ),
        ),
    )
    full_spec = full_compilation.request.output_composition
    secondary_output_path_b = None
    for t_b in full_spec.targets if full_spec is not None else ():
        if str(t_b.target_id) == "secondary_debug_workbook":
            secondary_output_path_b = str(t_b.output.path)
            break
    if not secondary_output_path_b:
        raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
    _ = inject_output_dir_conflict_for_target(output_path=str(secondary_output_path_b))
    full_core = run_ir(full_compilation.demand_ir, full_compilation.request)

    full_output_path = Path(str((full_core.outputs or {}).get("detail") or full_core.output_path or ""))
    full_rows = read_csv_rows(full_output_path) if full_output_path.exists() else []
    full_stats = stats_by_id(full_core.output_target_stats)

    return (
        full_compilation,
        full_core,
        full_output_path,
        full_rows,
        full_stats,
        out_root_detail_full,
    )


@app.cell
def _(
    ALLOWED_MODULES,
    DemandRunOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    DemandRunTemplateOptions,
    Dict,
    allowed_yaml_roots,
    compile_yaml,
    inject_output_dir_conflict_for_target,
    run_ir,
    tmp,
    yaml_all_fail_path,
):
    # 场景 C: all_fail 预期整体抛错
    out_root_detail_all_fail = tmp / "out_detail_all_fail"
    init_vars_all_fail: Dict[str, object] = {
        "out_path_detail": str(out_root_detail_all_fail),
        "out_path_secondary_workbook": str(tmp / "out_secondary_workbook"),
    }

    all_fail_ok = False
    all_fail_summary = ""
    try:
        all_fail_compilation = compile_yaml(
            str(yaml_all_fail_path),
            options=DemandRunOptions(
                security=DemandRunSecurityOptions(
                    allowed_modules=ALLOWED_MODULES,
                    allowed_yaml_roots=allowed_yaml_roots,
                ),
                template=DemandRunTemplateOptions(init_vars=init_vars_all_fail),
                runtime=DemandRunRuntimeOptions(
                    demand_failure_policy="all_fail",
                    batch_size=2,
                ),
            ),
        )
        all_fail_spec = all_fail_compilation.request.output_composition
        secondary_output_path_c = None
        for t_c in all_fail_spec.targets if all_fail_spec is not None else ():
            if str(t_c.target_id) == "secondary_debug_workbook":
                secondary_output_path_c = str(t_c.output.path)
                break
        if not secondary_output_path_c:
            raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
        _ = inject_output_dir_conflict_for_target(output_path=str(secondary_output_path_c))
        _ = run_ir(all_fail_compilation.demand_ir, all_fail_compilation.request)
        all_fail_summary = "unexpected: all_fail run succeeded"
    except Exception as exc:  # noqa: BLE001 — 预期异常：断言 all_fail 整体失败
        exc_msg = str(exc)
        all_fail_ok = bool("Output target failed" in exc_msg or "OutputTargetWriteError" in type(exc).__name__)
        all_fail_summary = "{}: {}".format(type(exc).__name__, exc_msg)

    print("all_fail_ok =", all_fail_ok)
    return all_fail_ok, all_fail_summary


@app.cell
def _(is_hex_64, out_root_detail_redacted, redacted_output_path, redacted_rows, redacted_stats, versioned_outputs):
    # 场景 A 校验
    redacted_ok = True
    if len(redacted_rows) != 5:
        redacted_ok = False
    if not redacted_output_path.exists():
        redacted_ok = False
    else:
        try:
            parsed = versioned_outputs.parse_versioned_output_path(redacted_output_path)
        except Exception:  # noqa: BLE001
            redacted_ok = False
        else:
            if parsed.root.resolve() != out_root_detail_redacted.resolve():
                redacted_ok = False
            if parsed.kind != "files" or parsed.artifact_id != "detail_csv":
                redacted_ok = False

    primary = redacted_stats.get("detail")
    secondary = redacted_stats.get("secondary_debug_workbook")
    if primary is None or secondary is None:
        redacted_ok = False
    else:
        if primary.disabled or int(primary.error_count) != 0:
            redacted_ok = False
        if (not secondary.disabled) or int(secondary.error_count) < 1:
            redacted_ok = False
        if not is_hex_64(secondary.error_message_hash):
            redacted_ok = False
        if str(secondary.error_message or "") != "sha256={}".format(str(secondary.error_message_hash or "")):
            redacted_ok = False

    print("redacted_ok =", redacted_ok)
    return redacted_ok


@app.cell
def _(full_output_path, full_rows, full_stats, is_hex_64, out_root_detail_full, versioned_outputs):
    # 场景 B 校验
    full_ok = True
    if len(full_rows) != 5:
        full_ok = False
    if not full_output_path.exists():
        full_ok = False
    else:
        try:
            parsed_full = versioned_outputs.parse_versioned_output_path(full_output_path)
        except Exception:  # noqa: BLE001
            full_ok = False
        else:
            if parsed_full.root.resolve() != out_root_detail_full.resolve():
                full_ok = False
            if parsed_full.kind != "files" or parsed_full.artifact_id != "detail_csv":
                full_ok = False

    full_secondary = full_stats.get("secondary_debug_workbook")
    if full_secondary is None:
        full_ok = False
    else:
        full_msg = str(full_secondary.error_message or "")
        if full_msg.startswith("sha256="):
            full_ok = False
        if not is_hex_64(full_secondary.error_message_hash):
            full_ok = False

    print("full_ok =", full_ok)
    return full_ok


@app.cell
def _(all_fail_ok, full_ok, redacted_ok, render_checks):
    checks = {
        "redacted 场景（primary 成功 + secondary 脱敏）": redacted_ok,
        "full 场景（完整错误信息）": full_ok,
        "all_fail 场景预期整体抛错": all_fail_ok,
    }
    render_checks(checks)
    return checks


@app.cell
def _(
    all_fail_ok,
    all_fail_summary,
    checks,
    full_core,
    full_ok,
    full_rows,
    make_chapter_result,
    redacted_core,
    redacted_ok,
    redacted_rows,
    summarize_stats,
    yaml_all_fail_path,
    yaml_full_path,
    yaml_redacted_path,
):
    passed = bool(all(checks.values()))
    if passed:
        summary = "expected failure captured: {}\nredacted_ok={} full_ok={} all_fail_ok={}".format(
            all_fail_summary, redacted_ok, full_ok, all_fail_ok
        )
    else:
        summary = "unexpected: redacted_ok={} full_ok={} all_fail_ok={} | {}".format(redacted_ok, full_ok, all_fail_ok, all_fail_summary)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"redacted_scenario_ok": True, "full_scenario_ok": True, "all_fail_raises": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "yaml_redacted": str(yaml_redacted_path),
            "yaml_full": str(yaml_full_path),
            "yaml_all_fail": str(yaml_all_fail_path),
            "detail_rows_redacted": len(redacted_rows),
            "detail_rows_full": len(full_rows),
            "redacted_output_target_stats": summarize_stats(redacted_core.output_target_stats),
            "full_output_target_stats": summarize_stats(full_core.output_target_stats),
            "all_fail_summary": all_fail_summary,
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
