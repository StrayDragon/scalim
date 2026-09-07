"""Cells-native marimo notebook: ch100_yaml_dsl_row_number_score_by_rank.

迁移对照:
  Before: 模块级 run_*() 持全部逻辑;cells 薄壳
  After:  运行/输出定位/oracle 校验全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_row_number_score_by_rank

        ## 回归点

        ecommerce rank/score 报表：`row_number` / `score` 计算与分档，
        产物 `rank_csv` 与纯 Python oracle（`verify_ecommerce_rank_score_csv_rows`）对拍。

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 配置 `build_test_config_small` + set_config
        2. `run`（ecommerce_rank_score_report.yaml）
        3. 输出定位 `rank_csv` + CSV 读取
        4. oracle 对拍断言
        5. 汇总 chapter_result

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
    yaml_path = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_rank_score_report.yaml"
    _ = repo_root
    return Path, demo_dir, yaml_path


@app.cell
def _(Path):
    import csv
    import tempfile
    from typing import Any, Dict, List, Optional

    from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
    from scalim.dsl.yaml_dsl import run as run_yaml
    from scalim.shortcuts.resources import outputs as outputs_api
    from scalim_misc.demo_big_data_report.by_yaml_dsl.ecommerce_rank_score_oracle import verify_ecommerce_rank_score_csv_rows
    from scalim_misc.demo_big_data_report.cases import build_test_config_small
    from scalim_misc.demo_big_data_report.loaders import ECommerceConfig, set_config
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return (
        Any,
        DemandRunOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        DemandRunTemplateOptions,
        Dict,
        ECommerceConfig,
        List,
        Optional,
        Path,
        build_test_config_small,
        csv,
        make_chapter_result,
        outputs_api,
        render_checks,
        run_yaml,
        set_config,
        tempfile,
        verify_ecommerce_rank_score_csv_rows,
    )


@app.cell
def _(Dict, List, Path, csv):
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

    return read_csv_rows


@app.cell
def _(Path, build_test_config_small, set_config, tempfile):
    import atexit
    import shutil

    cfg = build_test_config_small()
    set_config(cfg)
    ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.loaders"])

    tmp = Path(tempfile.mkdtemp(prefix="scalim-rank-score-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    out_root = tmp / "out"
    print("out_root:", out_root)
    return ALLOWED_MODULES, cfg, out_root, tmp


@app.cell
def _(ALLOWED_MODULES, DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions, Dict, out_root, run_yaml, yaml_path):
    init_vars: Dict[str, object] = {"out_root_rank": str(out_root)}
    result = run_yaml(
        str(yaml_path),
        options=DemandRunOptions(
            security=DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            template=DemandRunTemplateOptions(init_vars=init_vars),
            runtime=DemandRunRuntimeOptions(batch_size=10),
        ),
    )
    core = result.core
    print("total_rows =", core.total_rows)
    print("outputs    =", sorted(core.outputs.keys()) if core.outputs else None)
    return core, init_vars, result


@app.cell
def _(outputs_api, out_root, read_csv_rows):
    out_rank = outputs_api.latest_file_path(out_root, file_id="rank_csv")
    rows = read_csv_rows(out_rank) if out_rank.exists() else []
    print("rank_csv rows =", len(rows))
    return out_rank, rows


@app.cell
def _(cfg, core, render_checks, rows, verify_ecommerce_rank_score_csv_rows):
    ok_oracle, oracle_summary, oracle_details = verify_ecommerce_rank_score_csv_rows(actual_rows=rows, cfg=cfg)
    checks = {
        "oracle 对拍通过": ok_oracle,
        "输出行非空": bool(rows),
        "输出非空": bool(core.outputs),
    }
    render_checks(checks)
    return checks, ok_oracle, oracle_details, oracle_summary


@app.cell
def _(checks, core, make_chapter_result, ok_oracle, oracle_details, oracle_summary, out_rank, rows, yaml_path):
    passed = bool(all(checks.values()))
    summary = "oracle={} rows={} outputs={} | {}".format(
        ok_oracle, len(rows), sorted(core.outputs.keys()) if core.outputs else None, oracle_summary
    )
    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "yaml_path": str(yaml_path),
            "rank_csv": str(out_rank),
            "rows": len(rows),
            "outputs": core.outputs,
            "oracle": oracle_details,
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