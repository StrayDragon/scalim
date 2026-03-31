import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.execution.run_ir import run_ir
from scalim.ob.presets.execution_trace import ExecutionTraceObserver
from scalim.ob.presets.logs import LoggingObserver
from scalim.ob.presets.memory import MemoryOptimizationObserver
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_observability_full"
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


def _find_first_instance(components: Optional[Sequence[object]], cls: type) -> Optional[object]:
    for c in components or ():
        if isinstance(c, cls):
            return c
    return None


def _glob_viz_files(base_dir: Path) -> Dict[str, str]:
    # `viz` 输出目录结构:
    #   `<base_dir>/scalim-viz/run_<epoch_ms>/viz_*.{json,jsonl}`
    scalim_viz_dir = base_dir / "scalim-viz"
    run_dirs = sorted([p for p in scalim_viz_dir.glob("run_*") if p.is_dir()]) if scalim_viz_dir.exists() else []
    if len(run_dirs) != 1:
        return {"runs": str(len(run_dirs)), "dir": str(scalim_viz_dir)}
    run_dir = run_dirs[0]
    return {
        "run_dir": str(run_dir),
        "snapshot": str(run_dir / "viz_snapshot.json"),
        "events": str(run_dir / "viz_events.jsonl"),
        "trace": str(run_dir / "viz_trace.jsonl"),
    }


def run_yaml_dsl_observability_full(*, yaml_path: Optional[Path] = None) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_observability_full.yaml"

    with tempfile.TemporaryDirectory(prefix="scalim-ob-full-") as tmpdir:
        tmp = Path(tmpdir)
        out_detail = tmp / "detail.csv"
        viz_base_dir = tmp / "viz_out"

        template_vars: Dict[str, object] = {"viz_output_dir": str(viz_base_dir)}
        init_vars: Dict[str, object] = {"out_path_detail": str(out_detail)}

        try:
            compilation = compile_yaml(
                str(yaml_path),
                allowed_modules=_ALLOWED_MODULES,
                init_vars=init_vars,
                template_vars=template_vars,
            )
            trace_observer = _find_first_instance(compilation.request.components, ExecutionTraceObserver)
            memory_opt_observer = _find_first_instance(compilation.request.components, MemoryOptimizationObserver)
            logging_observer = _find_first_instance(compilation.request.components, LoggingObserver)
            core = run_ir(compilation.demand_ir, compilation.request)
        except Exception as exc:  # noqa: BLE001
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=False,
                kind=EXAMPLE_KIND_ORACLE,
                summary="compile/run failed: {}: {}".format(type(exc).__name__, exc),
                details={"exc_type": type(exc).__name__, "message": str(exc)},
            )

        rows = _read_csv_rows(out_detail) if out_detail.exists() else []
        trace = trace_observer if isinstance(trace_observer, ExecutionTraceObserver) else None
        mem = memory_opt_observer if isinstance(memory_opt_observer, MemoryOptimizationObserver) else None
        log = logging_observer if isinstance(logging_observer, LoggingObserver) else None

        viz_files = _glob_viz_files(viz_base_dir)
        snapshot_ok = Path(viz_files.get("snapshot") or "").exists() if "snapshot" in viz_files else False
        events_ok = Path(viz_files.get("events") or "").exists() if "events" in viz_files else False
        trace_ok_file = Path(viz_files.get("trace") or "").exists() if "trace" in viz_files else False

        # 固定 5 条 `tickets`, `batch_size=2` -> 3 个 `batch`(2,2,1)
        ok_trace = bool(trace and len(trace.batches) == 3 and trace.total_loader_calls >= 1)
        ok_memory = bool(mem and len(mem.row_write_events) >= 5)
        ok_logging = bool(log is not None)
        ok_viz = bool(snapshot_ok and events_ok and trace_ok_file)
        ok_rows = bool(len(rows) == 5 and core.total_rows == 5)

        passed = bool(ok_rows and ok_trace and ok_memory and ok_logging and ok_viz)
        summary = "rows={} trace={} memory_opt={} logging={} viz={}".format(ok_rows, ok_trace, ok_memory, ok_logging, ok_viz)

        details: Dict[str, Any] = {
            "yaml_path": str(yaml_path),
            "detail_csv": str(out_detail),
            "rows": len(rows),
            "core_total_rows": int(core.total_rows),
            "observers_present": {
                "logging": bool(log is not None),
                "trace": bool(trace is not None),
                "memory_opt": bool(mem is not None),
            },
            "trace_stats": {
                "batches": len(trace.batches) if trace else None,
                "total_loader_calls": int(trace.total_loader_calls) if trace else None,
                "total_row_writes": int(trace.total_row_writes) if trace else None,
            },
            "memory_opt_stats": {
                "field_slim_events": len(mem.field_slim_events) if mem else None,
                "row_write_events": len(mem.row_write_events) if mem else None,
                "row_release_events": len(mem.row_release_events) if mem else None,
            },
            "viz_files": viz_files,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_observability_full()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_observability_full

        ## 背景

        工程同学维护一份 YAML 报表时,真正“难排查”的通常不是语法错,而是运行期问题:

        - 为什么慢?（哪个 loader 慢 / 哪个批次慢）
        - 为什么缺?（keys 请求了多少,实际返回多少）
        - 为什么错?（哪里抛错,上下文是什么）
        - 为什么占内存?（字段瘦身/行释放是否按预期发生）

        Scalim 把这些变成可配置、可回归的 **observability**。

        ## 需求方提问（自然语言）

        维护者：我能不能只改 YAML 就打开/关闭这些观测能力,并且在 CI 里确定性验证它真的生效？

        ## 本章覆盖的 YAML DSL 能力

        - `observability.logging`：启用/关闭日志观测(本章用 `renderer: logger` 以保持安静)
        - `observability.trace`：执行追踪(批次级步骤)
        - `observability.viz`：可回放的事件/快照(`viz_snapshot.json` + `viz_events.jsonl` + `viz_trace.jsonl`)
        - `observability.memory_opt`：内存优化事件观测(字段瘦身/行释放等)
        - `template_vars`：用 `LiteJinja2` 在编译期注入 `viz.output_dir`(隔离输出路径)

        ## 对拍点（deterministic）

        - 批大小 `batch_size=2` 下,固定数据集(5 rows)应产生 3 个 batch trace
        - `viz` 输出目录下必须生成快照/事件/trace 文件
        - `memory_opt` 至少应记录到行写入事件(>=5)

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch080_yaml_dsl_observability_full.py::run_yaml_dsl_observability_full`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_observability_full.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Observability demand YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_observability_full(yaml_path=yaml_path)
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
