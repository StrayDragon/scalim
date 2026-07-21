import marimo

import csv
import logging
import tempfile
from pathlib import Path
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
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_output_failure_policy"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario"])


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if not row:
                continue
            rows.append({str(k): str(v) if v is not None else "" for k, v in row.items()})
    return rows


def _is_hex_64(value: Optional[str]) -> bool:
    if not value:
        return False
    v = str(value).strip().lower()
    if len(v) != 64:
        return False
    for ch in v:
        if ch not in "0123456789abcdef":
            return False
    return True


def _stats_by_id(stats: Optional[Sequence[OutputTargetStats]]) -> Dict[str, OutputTargetStats]:
    by_id: Dict[str, OutputTargetStats] = {}
    for s in stats or ():
        by_id[str(s.target_id)] = s
    return by_id


def _summarize_stats(stats: Optional[Sequence[OutputTargetStats]]) -> List[Dict[str, Any]]:
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


def _inject_output_dir_conflict_for_target(*, output_path: str) -> Path:
    """在“应为文件”的路径上预先创建同名目录,用于构造确定性的写入失败."""
    p = Path(str(output_path))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.mkdir(parents=False, exist_ok=True)
    return p


def run_yaml_dsl_output_failure_policy(
    *,
    yaml_redacted_path: Optional[Path] = None,
    yaml_full_path: Optional[Path] = None,
    yaml_all_fail_path: Optional[Path] = None,
) -> ExampleResult:
    demo_dir = Path(__file__).resolve().parents[1]
    support_dir = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support"
    allowed_yaml_roots = (str(support_dir.parent),)

    if yaml_redacted_path is None:
        yaml_redacted_path = support_dir / "support_output_failure_primary_only_redacted.yaml"
    if yaml_full_path is None:
        yaml_full_path = support_dir / "support_output_failure_primary_only_full.yaml"
    if yaml_all_fail_path is None:
        yaml_all_fail_path = support_dir / "support_output_failure_all_fail.yaml"

    with tempfile.TemporaryDirectory(prefix="scalim-output-failure-") as tmpdir:
        tmp = Path(tmpdir)
        out_root_secondary = tmp / "out_secondary_workbook"

        # 本章故意构造次输出写失败.为了让 `just examples` 输出更干净,临时把 `excel` 输出端的 `ERROR` 堆栈日志静音.
        sink_logger = logging.getLogger("scalim.sinks.sink_excel")
        prev_level = sink_logger.level
        sink_logger.setLevel(logging.CRITICAL)
        try:
            # -----------------------------------------------------------------
            # `primary_only` + 脱敏错误信息
            # -----------------------------------------------------------------
            out_root_detail_redacted = tmp / "out_detail_redacted"
            init_vars_redacted: Dict[str, object] = {
                "out_path_detail": str(out_root_detail_redacted),
                "out_path_secondary_workbook": str(out_root_secondary),
            }

            try:
                redacted_compilation = compile_yaml(
                    str(yaml_redacted_path),
                    options=DemandRunOptions(
                        security=DemandRunSecurityOptions(
                            allowed_modules=_ALLOWED_MODULES,
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
                secondary_output_path = None
                for t in redacted_spec.targets if redacted_spec is not None else ():
                    if str(t.target_id) == "secondary_debug_workbook":
                        secondary_output_path = str(t.output.path)
                        break
                if not secondary_output_path:
                    raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
                _ = _inject_output_dir_conflict_for_target(output_path=str(secondary_output_path))
                redacted_core = run_ir(redacted_compilation.demand_ir, redacted_compilation.request)
            except Exception as exc:  # noqa: BLE001
                return ExampleResult(
                    example_id=_EXAMPLE_ID,
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary="primary_only(redacted) unexpectedly failed: {}: {}".format(type(exc).__name__, exc),
                    details={"exc_type": type(exc).__name__, "message": str(exc)},
                )

            redacted_output_path = Path(str((redacted_core.outputs or {}).get("detail") or redacted_core.output_path or ""))
            redacted_rows = _read_csv_rows(redacted_output_path) if redacted_output_path.exists() else []
            redacted_stats = _stats_by_id(redacted_core.output_target_stats)

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
                if not _is_hex_64(secondary.error_message_hash):
                    redacted_ok = False
                if str(secondary.error_message or "") != "sha256={}".format(str(secondary.error_message_hash or "")):
                    redacted_ok = False

            # -----------------------------------------------------------------
            # `primary_only` + 完整错误信息
            # -----------------------------------------------------------------
            out_root_detail_full = tmp / "out_detail_full"
            init_vars_full: Dict[str, object] = {
                "out_path_detail": str(out_root_detail_full),
                "out_path_secondary_workbook": str(out_root_secondary),
            }

            try:
                full_compilation = compile_yaml(
                    str(yaml_full_path),
                    options=DemandRunOptions(
                        security=DemandRunSecurityOptions(
                            allowed_modules=_ALLOWED_MODULES,
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
                secondary_output_path = None
                for t in full_spec.targets if full_spec is not None else ():
                    if str(t.target_id) == "secondary_debug_workbook":
                        secondary_output_path = str(t.output.path)
                        break
                if not secondary_output_path:
                    raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
                _ = _inject_output_dir_conflict_for_target(output_path=str(secondary_output_path))
                full_core = run_ir(full_compilation.demand_ir, full_compilation.request)
            except Exception as exc:  # noqa: BLE001
                return ExampleResult(
                    example_id=_EXAMPLE_ID,
                    passed=False,
                    kind=EXAMPLE_KIND_ORACLE,
                    summary="primary_only(full) unexpectedly failed: {}: {}".format(type(exc).__name__, exc),
                    details={"exc_type": type(exc).__name__, "message": str(exc)},
                )

            full_output_path = Path(str((full_core.outputs or {}).get("detail") or full_core.output_path or ""))
            full_rows = _read_csv_rows(full_output_path) if full_output_path.exists() else []
            full_stats = _stats_by_id(full_core.output_target_stats)

            full_ok = True
            if len(full_rows) != 5:
                full_ok = False
            if not full_output_path.exists():
                full_ok = False
            else:
                try:
                    parsed = versioned_outputs.parse_versioned_output_path(full_output_path)
                except Exception:  # noqa: BLE001
                    full_ok = False
                else:
                    if parsed.root.resolve() != out_root_detail_full.resolve():
                        full_ok = False
                    if parsed.kind != "files" or parsed.artifact_id != "detail_csv":
                        full_ok = False

            full_secondary = full_stats.get("secondary_debug_workbook")
            if full_secondary is None:
                full_ok = False
            else:
                msg = str(full_secondary.error_message or "")
                if msg.startswith("sha256="):
                    full_ok = False
                if not _is_hex_64(full_secondary.error_message_hash):
                    full_ok = False

            # -----------------------------------------------------------------
            # `all_fail` 预期抛错
            # -----------------------------------------------------------------
            out_root_detail_all_fail = tmp / "out_detail_all_fail"
            init_vars_all_fail: Dict[str, object] = {
                "out_path_detail": str(out_root_detail_all_fail),
                "out_path_secondary_workbook": str(out_root_secondary),
            }

            all_fail_ok = False
            all_fail_summary = ""
            try:
                all_fail_compilation = compile_yaml(
                    str(yaml_all_fail_path),
                    options=DemandRunOptions(
                        security=DemandRunSecurityOptions(
                            allowed_modules=_ALLOWED_MODULES,
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
                secondary_output_path = None
                for t in all_fail_spec.targets if all_fail_spec is not None else ():
                    if str(t.target_id) == "secondary_debug_workbook":
                        secondary_output_path = str(t.output.path)
                        break
                if not secondary_output_path:
                    raise ValueError("output_composition 中缺少输出 target_id=`secondary_debug_workbook`")
                _ = _inject_output_dir_conflict_for_target(output_path=str(secondary_output_path))
                _ = run_ir(all_fail_compilation.demand_ir, all_fail_compilation.request)
                all_fail_summary = "unexpected: all_fail run succeeded"
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                all_fail_ok = bool("Output target failed" in msg or "OutputTargetWriteError" in type(exc).__name__)
                all_fail_summary = "{}: {}".format(type(exc).__name__, msg)

            passed = bool(redacted_ok and full_ok and all_fail_ok)
            if passed:
                summary = "expected failure captured: {}\nredacted_ok={} full_ok={} all_fail_ok={}".format(
                    all_fail_summary, redacted_ok, full_ok, all_fail_ok
                )
            else:
                summary = "unexpected: redacted_ok={} full_ok={} all_fail_ok={} | {}".format(
                    redacted_ok, full_ok, all_fail_ok, all_fail_summary
                )

            details: Dict[str, Any] = {
                "yaml_redacted": str(yaml_redacted_path),
                "yaml_full": str(yaml_full_path),
                "yaml_all_fail": str(yaml_all_fail_path),
                "detail_rows_redacted": len(redacted_rows),
                "detail_rows_full": len(full_rows),
                "redacted_output_target_stats": _summarize_stats(redacted_core.output_target_stats),
                "full_output_target_stats": _summarize_stats(full_core.output_target_stats),
                "all_fail_summary": all_fail_summary,
            }
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=passed,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details=details,
            )
        finally:
            sink_logger.setLevel(prev_level)


def run_chapter():
    """SSOT 入口：headless runner 与 pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_output_failure_policy

        ## 背景

        真实工程里,一个报表经常不止一个输出目标:

        - 主输出: 给业务方的“最终产物”(例如 `CSV` / `Excel`)
        - 次输出: 给工程同学排查问题的 debug 产物(例如额外的 `workbook` / `audit`)

        但次输出有时会因为路径冲突/权限/并发锁等原因失败。此时到底要不要阻断主输出,通常取决于业务场景:

        - 财务/对账: **任一输出失败即失败**(更强一致性)
        - 运营/日报: **主输出必须成功,次输出失败不阻断**(更强可用性)

        ## 需求方提问（自然语言）

        平台同学：能不能在运行入口侧声明“失败策略”,并在 YAML 里声明“错误信息是否脱敏”,并且在 CI 里确定性对拍？

	        ## 本章覆盖的能力
	
	        - runtime `demand_failure_policy`: `all_fail` / `primary_only`
	        - runtime `demand_diagnostics.include_full_error_message`: `false`(默认脱敏) / `true`(包含全文)
	        - `imports` + **scoped** `$import`：在 `main_source.*` / `resources.*` 复用 base 片段(输出 `outputs.*` 不支持 `$import`)

        ## 对拍点（deterministic）

	        - `primary_only`：次输出写失败时,主输出仍然成功,且 stats 记录该输出已被禁用
	        - `all_fail`：次输出写失败时,整体必须失败
	        - `demand_diagnostics.include_full_error_message=false`：错误信息以 `sha256=...` 形式脱敏
	        - `demand_diagnostics.include_full_error_message=true`：错误信息包含全文

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch070_yaml_dsl_output_failure_policy.py::run_yaml_dsl_output_failure_policy`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    support_dir = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support"
    yaml_redacted_path = support_dir / "support_output_failure_primary_only_redacted.yaml"
    yaml_full_path = support_dir / "support_output_failure_primary_only_full.yaml"
    yaml_all_fail_path = support_dir / "support_output_failure_all_fail.yaml"
    return demo_dir, support_dir, yaml_all_fail_path, yaml_full_path, yaml_redacted_path


@app.cell(hide_code=True)
def _(mo, yaml_redacted_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## YAML 片段：`imports` + `main_source/resources.$import` + 输出配置(head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_redacted_path, max_lines=80)))
    return (excerpt_head,)


@app.cell
def _(yaml_all_fail_path, yaml_full_path, yaml_redacted_path):
    result = run_yaml_dsl_output_failure_policy(
        yaml_redacted_path=yaml_redacted_path,
        yaml_full_path=yaml_full_path,
        yaml_all_fail_path=yaml_all_fail_path,
    )
    return (result,)


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
