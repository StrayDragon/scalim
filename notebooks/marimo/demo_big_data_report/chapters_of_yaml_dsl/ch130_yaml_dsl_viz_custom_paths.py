import marimo

import csv
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.dsl.by_yaml import compile as compile_yaml
from scalim.dsl.by_yaml import RunOverrides
from scalim.execution.run_ir import run_ir
from scalim.ob.presets.viz import VizObserverConfig
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_viz_custom_paths"
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


def run_yaml_dsl_viz_custom_paths(*, yaml_path: Optional[Path] = None) -> ExampleResult:
    if yaml_path is None:
        demo_dir = Path(__file__).resolve().parents[1]
        yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_viz_custom_paths.yaml"

    with tempfile.TemporaryDirectory(prefix="scalim-viz-custom-") as tmpdir:
        tmp = Path(tmpdir)
        out_detail = tmp / "detail.csv"
        viz_events = tmp / "viz_events.jsonl"
        viz_snapshot = tmp / "viz_snapshot.json"
        viz_trace = tmp / "viz_trace.jsonl"

        init_vars: Dict[str, object] = {"out_path_detail": str(out_detail)}
        overrides = RunOverrides(
            viz_config=VizObserverConfig(
                output_path=str(viz_events),
                snapshot_path=str(viz_snapshot),
                trace_enabled=True,
                payload_policy="sample",
                sample_size=2,
                append=False,
                run_name="support-viz-custom-paths",
                env="ci",
            )
        )

        try:
            compilation = compile_yaml(
                str(yaml_path),
                allowed_modules=_ALLOWED_MODULES,
                batch_size=2,
                init_vars=init_vars,
                overrides=overrides,
            )
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
        events_ok = viz_events.exists() and viz_events.stat().st_size > 0
        snapshot_ok = viz_snapshot.exists() and viz_snapshot.stat().st_size > 0
        trace_ok = viz_trace.exists() and viz_trace.stat().st_size > 0

        snapshot_meta: Dict[str, Any] = {}
        if snapshot_ok:
            snapshot_meta = json.loads(viz_snapshot.read_text(encoding="utf-8")).get("meta") or {}
        viz_meta = snapshot_meta.get("viz") if isinstance(snapshot_meta, dict) else {}
        run_name_ok = isinstance(viz_meta, dict) and viz_meta.get("run_name") == "support-viz-custom-paths"
        env_ok = isinstance(viz_meta, dict) and viz_meta.get("env") == "ci"

        passed = bool(len(rows) == 5 and events_ok and snapshot_ok and trace_ok and run_name_ok and env_ok and core.outputs)
        summary = "rows={} events={} snapshot={} trace={} run_name={} env={} outputs={}".format(
            len(rows),
            events_ok,
            snapshot_ok,
            trace_ok,
            run_name_ok,
            env_ok,
            sorted(core.outputs.keys()) if core.outputs else None,
        )

        details: Dict[str, Any] = {
            "yaml_path": str(yaml_path),
            "detail_csv": str(out_detail),
            "rows": len(rows),
            "viz_paths": {
                "events": str(viz_events),
                "snapshot": str(viz_snapshot),
                "trace": str(viz_trace),
            },
            "snapshot_meta_viz": viz_meta,
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter() -> ExampleResult:
    return run_yaml_dsl_viz_custom_paths()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_viz_custom_paths

        ## 背景

        `viz` 输出默认会在 `output_dir/scalim-viz/<run_id>/...` 下落盘。
        但在工程落地里,经常需要把这些产物写到“固定路径”,方便:
        - CI artifacts 采集
        - 上传对象存储/接入外部调试平台

        ## 需求方提问（自然语言）

        平台同学：我能不能显式指定 `viz` 的输出文件路径,不依赖 run 目录推导？

        ## 本章覆盖的 runtime entrypoints 能力

        - `overrides=RunOverrides(viz_config=...)`
          - `VizObserverConfig.output_path`：事件 `JSONL` 的显式输出路径
          - `VizObserverConfig.snapshot_path`：快照 `JSON` 的显式输出路径

        ## 对拍点（deterministic）

        - YAML fixture：`chapters_of_yaml_dsl/declared_yaml_dsl/support/support_viz_custom_paths.yaml`
        - 断言:
          - events/snapshot/trace 三个文件都存在且非空
          - snapshot 的 `meta.viz.run_name/env` 与 YAML 一致

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch130_yaml_dsl_viz_custom_paths.py::run_yaml_dsl_viz_custom_paths`
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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "support" / "support_viz_custom_paths.yaml"
    return demo_dir, yaml_path


@app.cell(hide_code=True)
def _(mo, yaml_path):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Viz custom paths YAML (head)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(yaml_path, max_lines=140)))
    return (excerpt_head,)


@app.cell
def _(yaml_path):
    result = run_yaml_dsl_viz_custom_paths(yaml_path=yaml_path)
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
