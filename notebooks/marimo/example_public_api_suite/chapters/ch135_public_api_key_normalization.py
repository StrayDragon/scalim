"""Cells-native marimo notebook: ch135_public_api_key_normalization.

迁移对照:
  Before: 模块级 run_public_api_key_normalization() 持全部逻辑;cells 薄壳 +
          自引用 chapter_result 残留
  After:  raw/auto_str 双 run 对照全部在 cells 内
"""

import marimo

__generated_with = "0.22.0"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # example_public_api_suite / ch135_public_api_key_normalization

        本章目标:
        - 演示 `key_normalization` 在 relations 场景下如何统一 key 口径

        场景:
        - 主源 `dim_id` 为 `"1"`（`str`）
        - 维表 `mapping` 的 `key` 为 `1`（`int`）且为 `preload_forever` 缓存源

        期望:
        - `raw` 下 `miss` → `dim_name=None`
        - `auto_str` 下命中 → `dim_name="One"`

        ## 主线装配过程（每个步骤一个 cell，可就地修改重跑）

        1. 内联 demand YAML（行列表 join）
        2. `raw` 运行 → 断言 miss
        3. `auto_str` 运行 → 断言命中
        4. 断言展开 → chapter_result

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
    from typing import Any, Dict, FrozenSet, Optional

    from scalim.dsl import yaml_dsl as api
    from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

    return Any, Dict, FrozenSet, Optional, Path, api, make_chapter_result, render_checks


@app.cell
def _(Optional, Path):
    # 零件: 文本写入 / 首行 dim_name 提取
    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    def first_dim_name(rows: Any) -> Optional[object]:
        if not rows:
            return None
        return rows[0].get("dim_name")

    return first_dim_name, write_text


@app.cell
def _(FrozenSet, Path, api, write_text):
    import atexit
    import shutil
    import tempfile

    ALLOWED_MODULES: FrozenSet[str] = frozenset(["scalim_misc.examples.public_api._fixtures"])

    tmp = Path(tempfile.mkdtemp(prefix="scalim-pubapi-135-"))
    atexit.register(lambda: shutil.rmtree(tmp, ignore_errors=True))
    demand_path = tmp / "demand.yaml"

    demand_yaml = "\n".join(
        [
            "name: public_api_key_normalization_demo",
            "",
            "main_source:",
            "  source_id: items",
            '  loader: "scalim_misc.examples.public_api._fixtures:load_items_key_normalization_demo"',
            "  fields:",
            "    item_id: {extract: item_id, name: Item ID}",
            "    dim_id: {extract: dim_id, name: Dim ID}",
            "",
            "relations:",
            "  items_to_dims:",
            "    steps:",
            "      - from: items.dim_id",
            "        to: dims.dim_id",
            "",
            "sources:",
            "  dims:",
            '    loader: "scalim_misc.examples.public_api._fixtures:load_dims_key_normalization_demo_int_keys"',
            "    key: dim_id",
            "    cache_mode: preload_forever",
            "    fields:",
            "      dim_name:",
            "        name: Dim Name",
            "        relation: items_to_dims",
        ]
    )
    write_text(demand_path, demand_yaml)
    print("demand_path:", demand_path)
    return ALLOWED_MODULES, demand_path, tmp


@app.cell
def _(ALLOWED_MODULES, api, demand_path):
    # raw: key 类型不一致 -> miss
    result_raw = api.run(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(key_normalization="raw", batch_size=10),
            outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
        ),
    )
    captured_raw = result_raw.captured_rows
    raw_rows = [] if captured_raw is None else list(captured_raw.iter_row_data())
    print("raw rows =", len(raw_rows))
    return raw_rows, result_raw


@app.cell
def _(ALLOWED_MODULES, api, demand_path):
    # auto_str: 统一 key 口径 -> 命中
    result_norm = api.run(
        str(demand_path),
        options=api.DemandRunOptions(
            security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
            runtime=api.DemandRunRuntimeOptions(key_normalization="auto_str", batch_size=10),
            outputs=api.DemandRunOutputOptions(capture=api.CaptureRows()),
        ),
    )
    captured_norm = result_norm.captured_rows
    norm_rows = [] if captured_norm is None else list(captured_norm.iter_row_data())
    print("auto_str rows =", len(norm_rows))
    return norm_rows, result_norm


@app.cell
def _(first_dim_name, norm_rows, raw_rows, render_checks):
    raw_dim_name = first_dim_name(raw_rows)
    norm_dim_name = first_dim_name(norm_rows)
    checks = {
        "raw 下 miss（dim_name=None）": raw_dim_name is None,
        "auto_str 下命中（dim_name=One）": norm_dim_name == "One",
        "两类输出均非空": bool(raw_rows) and bool(norm_rows),
    }
    render_checks(checks)
    return checks, norm_dim_name, raw_dim_name


@app.cell
def _(checks, make_chapter_result, norm_dim_name, norm_rows, raw_dim_name, raw_rows):
    passed = bool(all(checks.values()))
    summary = "raw_dim_name={} normalized_dim_name={}".format(raw_dim_name, norm_dim_name)
    # 对拍期望（教学 payload；headless 可经 details 键定位）
    expected = {"raw_dim_name_is_none": True, "norm_dim_name": "One", "both_outputs_nonempty": True}
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "raw_dim_name": raw_dim_name,
            "normalized_dim_name": norm_dim_name,
            "raw_rows": raw_rows,
            "normalized_rows": norm_rows,
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
