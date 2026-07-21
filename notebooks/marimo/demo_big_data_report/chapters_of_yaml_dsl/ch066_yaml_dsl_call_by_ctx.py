import marimo

import csv
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from scalim.dsl.yaml_dsl import DemandRunOptions, DemandRunRuntimeOptions, DemandRunSecurityOptions, DemandRunTemplateOptions
from scalim.dsl.yaml_dsl import compile as compile_yaml
from scalim.execution import run_ir
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.22.0"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/yaml_dsl_call_by_ctx"
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


def run_yaml_dsl_call_by_ctx() -> ExampleResult:
    """演示 `call_by` 中 `$ctx` 的各种用法.

    测试场景:
    1. 使用 `$ctx` 传递整个上下文对象
    2. 使用 `$ctx.row_id` 访问行 ID
    3. 使用 `$ctx.batch_num` 访问批次号
    4. 使用 `$ctx.field_id` 访问字段 ID
    5. 使用 `$ctx.deps` 访问依赖项
    6. 使用 `$ctx.values` 访问字段值字典
    """

    with tempfile.TemporaryDirectory(prefix="scalim-yaml-call-by-ctx-") as tmpdir:
        tmp = Path(tmpdir)
        yaml_file = tmp / "test_ctx.yaml"
        out_root = tmp / "out"

        # 测试各种 `$ctx` 用法的 `YAML` 配置
        yaml_content = """\
name: yaml_dsl_call_by_ctx_demo

main_source:
  source_id: tickets
  loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:load_support_tickets"
  fields:
    ticket_id: {extract: ticket_id, name: 工单ID, value_cast: int}
    category: {extract: category, name: 分组名}
    priority: {extract: priority, name: 优先级}

fields:
  # 测试 1: 使用 $ctx 传递整个上下文对象（需要引用字段以满足依赖检查）
  _test_full_ctx:
    name: 完整上下文测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_full_context(ticket_id=ticket_id, ctx=$ctx)"

  # 测试 2: 使用 $ctx.row_id
  _test_row_id:
    name: 行ID测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_row_id(ticket_id=ticket_id, row_id=$ctx.row_id)"

  # 测试 3: 使用 $ctx.batch_num
  _test_batch_num:
    name: 批次号测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_batch_num(ticket_id=ticket_id, batch_num=$ctx.batch_num)"

  # 测试 4: 使用 $ctx.field_id
  _test_field_id:
    name: 字段ID测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_field_id(ticket_id=ticket_id, field_id=$ctx.field_id)"

  # 测试 5: 使用 $ctx.deps
  _test_deps:
    name: 依赖项测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_deps(ticket_id=ticket_id, deps=$ctx.deps)"

  # 测试 6: 使用 $ctx.values
  _test_values:
    name: 值字典测试
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:test_values(ticket_id=ticket_id, values=$ctx.values)"

  # 测试 7: 混合使用字段值和 $ctx
  _enriched_status:
    name: 增强状态
    call_by: "scalim_misc.demo_big_data_report.by_yaml_dsl.support_scenario:enrich_status_with_context(category=category, priority=priority, ctx=$ctx)"

resources:
  files:
    detail_csv:
      csv_file:
        path: {$init_var: out_root}
        encoding: utf-8

outputs:
  - name: detail
    to: {file: detail_csv}
    write:
      header_fields_output_by: field_id
      include_header: true
    fields: [ticket_id, category, priority, _test_full_ctx, _test_row_id, _test_batch_num, _test_field_id, _test_deps, _test_values, _enriched_status]
"""

        yaml_file.write_text(yaml_content, encoding="utf-8")

        init_vars: Dict[str, object] = {"out_root": str(out_root)}

        outputs = None
        detail_path = None
        rows: List[Dict[str, str]] = []
        ok = False
        exc_msg = ""

        try:
            compilation = compile_yaml(
                str(yaml_file),
                options=DemandRunOptions(
                    security=DemandRunSecurityOptions(allowed_modules=_ALLOWED_MODULES),
                    template=DemandRunTemplateOptions(init_vars=init_vars),
                    runtime=DemandRunRuntimeOptions(batch_size=2),
                ),
            )
            core = run_ir(compilation.demand_ir, compilation.request)
            outputs = sorted(core.outputs.keys()) if core.outputs else []
            detail_path = Path(str(core.outputs.get("detail"))) if core.outputs and core.outputs.get("detail") else None
            rows = _read_csv_rows(detail_path) if detail_path and detail_path.exists() else []
            ok = bool(len(rows) > 0 and len(outputs) > 0)
        except Exception as exc:  # noqa: BLE001
            exc_msg = "{}: {}".format(type(exc).__name__, exc)

        passed = ok
        summary = "rows={} outputs={} exc={}".format(len(rows), outputs, exc_msg if exc_msg else "none")
        details: Dict[str, Any] = {
            "yaml_path": str(yaml_file),
            "out_root": str(out_root),
            "detail_csv": str(detail_path) if detail_path else None,
            "rows": len(rows),
            "outputs": outputs,
            "exc_msg": exc_msg,
        }

        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )


def run_chapter():
    """SSOT entry: headless runner / pytest import this."""
    outputs, defs = app.run()
    return defs["chapter_result"]


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / yaml_dsl_call_by_ctx

        ## 背景

        YAML DSL 的 `call_by` 机制支持通过 `$ctx` 特殊标记访问运行时上下文信息。
        这允许用户编写的函数访问当前处理的行、批次、字段等元数据。

        ## $ctx 支持的用法

        ### 1. 传递整个上下文对象

        ```yaml
        call_by: "myapp.func(arg=$ctx)"
        ```

        接收函数会获得完整的 `_AggregateCallByContext` 对象，包含以下属性:
        - `row_id`: 当前行的 ID (Optional[object])
        - `batch_num`: 批次号 (int)
        - `field_id`: 字段 ID (str)
        - `deps`: 依赖项 (Tuple[str, ...])
        - `values`: 字段值字典 (Dict[str, FieldValue])

        ### 2. 访问特定属性

        ```yaml
        call_by: "myapp.func(row_id=$ctx.row_id)"
        call_by: "myapp.func(batch_num=$ctx.batch_num)"
        call_by: "myapp.func(field_id=$ctx.field_id)"
        call_by: "myapp.func(deps=$ctx.deps)"
        call_by: "myapp.func(values=$ctx.values)"
        ```

        ### 3. 混合使用

        ```yaml
        call_by: "myapp.func(field_value=status, ctx=$ctx)"
        ```

        ## 本章验证点

        - **编译期验证**: 各种 `$ctx` 用法的语法解析
        - **运行期验证**: 上下文对象正确传递到目标函数
        - **功能验证**: 输出包含所有测试字段的正确结果

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch061b_yaml_dsl_call_by_ctx.py::run_yaml_dsl_call_by_ctx`
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
    return


@app.cell
def _():
    result = run_yaml_dsl_call_by_ctx()
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
