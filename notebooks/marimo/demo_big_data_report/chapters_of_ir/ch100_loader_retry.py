"""Cells-native: ch100_loader_retry — YAML DSL loader retry policy.

设计目标（对齐 repo 金标准 `chapters_of_ir/ch010_basics`）:
- 本章走 **YAML DSL** 声明式路径(`scalim.dsl.yaml_dsl.run`),并用 `loader_retry_demo_mod`
  作为**可复用 fixture 零件**(Loader + 抛 TransientError/ShouldRetry 判定)。
- 主线装配(写 YAML → 注入 LoaderRetry → 运行 → 对拍)全部在 cells 内**逐 cell 展开**,
  并在**装配窥视 cell** 把 YAML 驱动配置 / `LoaderRetryPoliciesSpec` / 运行 options 直接渲染出来,
  读者无需跳库即可看到装配是怎样构成的。
- 通过 `chapter_result` 向 headless runner / pytest 暴露对拍结果（含 r1114 `expected` 快照）。
"""

import marimo

__generated_with = "0.23.14"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / ch100_loader_retry

        本章演示 YAML DSL 运行时 **LoaderRetryPolicy**(loader 重试策略):
        - **不开启**:loader 抛瞬时错误(`TransientError`)→ 运行失败
        - **开启** (`loader_retry`):按 `should_retry` 判定 + `max_attempts` 重试 → 成功

        主线装配过程(每个步骤一个 cell,可就地修改重跑):
        1. 准备 demand YAML(声明式主源 `orders` + loader 引用)+ 配置 `allowed_modules`
        2. 构造重试策略 `LoaderRetryPoliciesSpec` / `LoaderRetryPolicySpec`(`enabled + should_retry + max_attempts=2`)
        3. 组装两次 `DemandRunOptions`(`no_retry` 不注入重试 → 预期失败;`with_retry` 注入重试 → 预期成功)
        4. **(装配窥视)** 渲染 YAML 配置 / 重试 spec / 运行 options(读者无需跳库)
        5. 无重试运行(`run(...)`):预期抛 `TransientError`;注入重试后运行:预期重试后成功并捕获行
        6. `make_chapter_result(passed, summary, details={...})` 产出 `chapter_result`(含 `expected` 快照)

        > 本章 loader / 异常 / 重试判定来自 `loader_retry_demo_mod`(可复用 fixture 零件),
        > 完整的 `run()` 装配、重试注入与运行 options 在下方 cells + 装配窥视 cell 内可见。

        对拍入口: `run_chapter()` → `app.run()` → `chapter_result`
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
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    repo_root = ensure_repo_root_on_sys_path(__file__)
    _ = repo_root
    return (repo_root,)


@app.cell
def _():
    import tempfile
    import textwrap
    from pathlib import Path
    from typing import Dict

    from scalim.dsl.yaml_dsl import (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        run,
    )
    from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
    from scalim_misc.demo_big_data_report.by_yaml_dsl import loader_retry_demo_mod as demo_mod
    from scalim_misc.notebook_support.chapter_result import make_chapter_result

    return (
        CaptureRows,
        DemandRunOptions,
        DemandRunOutputOptions,
        DemandRunRuntimeOptions,
        DemandRunSecurityOptions,
        Dict,
        LoaderRetryPoliciesSpec,
        LoaderRetryPolicySpec,
        Path,
        demo_mod,
        make_chapter_result,
        run,
        tempfile,
        textwrap,
    )


@app.cell
def _(Path, demo_mod, tempfile, textwrap):
    # ① 准备 demand YAML 声明 + 允许模块白名单
    #    - 声明式主源 orders + loader 引用(指向 fixture 模块的 load_orders)
    #    - allowed_modules: 供 DSL 安全载入的模块白名单(fixture 模块)
    demand_yaml = textwrap.dedent("""
        name: loader_retry_demo
        main_source:
          source_id: orders
          loader: "scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              {}
    """).lstrip()
    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.by_yaml_dsl.loader_retry_demo_mod"])
    print("demand YAML prepared, allowed_modules OK")
    return allowed_modules, demand_yaml


@app.cell(hide_code=True)
def _(demand_yaml, mo):
    # ② 装配窥视(YAML DSL 声明可见,读者无需跳库):把驱动配置直接渲染出来
    mo.vstack(
        [
            mo.md("**装配窥视（读者无需跳库）**: 本章通过 **YAML DSL** 驱动 scalim,核心配置如下:"),
            mo.md("`demand_yaml`(需求 DSL,交给 `scalim.dsl.yaml_dsl.run(..., options=...)` 解析执行):"),
            mo.md("```yaml\n{}\n```".format(demand_yaml)),
        ]
    )
    return


@app.cell
def _(
    CaptureRows,
    DemandRunOptions,
    DemandRunOutputOptions,
    DemandRunRuntimeOptions,
    DemandRunSecurityOptions,
    LoaderRetryPoliciesSpec,
    LoaderRetryPolicySpec,
    allowed_modules,
    demo_mod,
):
    # ③ 构造重试策略 spec + 两次运行的 DemandRunOptions(scalim 装配)
    #    - LoaderRetryPolicySpec: enable=true + should_retry(只对 TransientError 重试) + max_attempts=2
    #    - LoaderRetryPoliciesSpec: 包装为默认策略,经 DemandRunRuntimeOptions.loader_retry 注入
    injected_retry = LoaderRetryPoliciesSpec(
        default=LoaderRetryPolicySpec(
            enabled=True,
            should_retry=demo_mod.should_retry,
            max_attempts=2,
            max_elapsed_seconds=5.0,
            backoff="fixed",
            base_delay_seconds=0.0,
            max_delay_seconds=0.0,
            jitter=False,
        )
    )
    #    - no_retry_options: 只注入安全白名单,不注入重试 → load_orders 首调抛 TransientError 直接失败
    #    - retry_options:  额外注入 loader_retry 与 CaptureRows 收行
    no_retry_options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
    )
    retry_options = DemandRunOptions(
        security=DemandRunSecurityOptions(allowed_modules=allowed_modules),
        runtime=DemandRunRuntimeOptions(loader_retry=injected_retry),
        outputs=DemandRunOutputOptions(capture=CaptureRows()),
    )
    return injected_retry, no_retry_options, retry_options


@app.cell(hide_code=True)
def _(injected_retry, mo, no_retry_options, retry_options):
    # ④ 装配窥视(读者无需跳库):把重试策略 spec 与两次运行的 options 差异直接渲染出来
    policy = injected_retry.default
    retry_fields = [
        {"key": "enabled", "value": policy.enabled},
        {"key": "should_retry", "value": getattr(policy.should_retry, "__name__", repr(policy.should_retry))},
        {"key": "max_attempts", "value": policy.max_attempts},
        {"key": "max_elapsed_seconds", "value": policy.max_elapsed_seconds},
        {"key": "backoff", "value": policy.backoff},
        {"key": "base_delay_seconds", "value": policy.base_delay_seconds},
        {"key": "jitter", "value": policy.jitter},
    ]
    option_rows = [
        {"run": "no_retry (预期失败)", "loader_retry": "未注入(默认 disabled)", "capture": "未注入"},
        {"run": "with_retry (预期成功)", "loader_retry": "injected_retry(default enabled, max_attempts=2)", "capture": "CaptureRows()"},
    ]
    mo.vstack(
        [
            mo.md(
                "**装配窥视（读者无需跳库）**: 本章构造的 `LoaderRetryPoliciesSpec` / `LoaderRetryPolicySpec` 如下,"
                "并通过 `DemandRunRuntimeOptions.loader_retry` 注入运行:"
            ),
            mo.ui.table(retry_fields, selection=None),
            mo.md("两次运行的 `DemandRunOptions` 差异(**仅**注入 `loader_retry` 与 `CaptureRows`,其余逻辑一致):"),
            mo.ui.table(option_rows, selection=None),
        ]
    )
    return


@app.cell
def _(
    Path,
    allowed_modules,
    demand_yaml,
    demo_mod,
    no_retry_options,
    retry_options,
    run,
    tempfile,
):
    # ⑤ 运行:用同一份 YAML + 同一 loader 跑两次(无重试 / 有重试),验证重试控制是否生效
    with tempfile.TemporaryDirectory() as tmpdir:
        demand_path = Path(tmpdir) / "demand.yaml"
        demand_path.write_text(demand_yaml, encoding="utf-8")

        # 5a) 无重试:loader 抛 TransientError → run() 向上抛出 → no_retry_ok=True
        demo_mod.reset()
        no_retry_ok = False
        try:
            run(str(demand_path), options=no_retry_options)
        except demo_mod.TransientError:
            no_retry_ok = True

        # 5b) 有重试:首调仍抛 TransientError,但 should_retry 判定后被重试,第二次成功
        demo_mod.reset()
        result = run(str(demand_path), options=retry_options)
        captured = result.captured_rows
        captured_rows = [] if captured is None else list(captured.iter_row_data())
        #     capture 命中 1 行(orders.order_id=1),且 loader 被调了 2 次(1 次失败 + 1 次成功)
        with_retry_ok = captured_rows == [{"order_id": 1}] and demo_mod.get_call_count() == 2

    print("no_retry_ok={} with_retry_ok={} call_count={}".format(no_retry_ok, with_retry_ok, demo_mod.get_call_count()))
    return no_retry_ok, with_retry_ok


@app.cell
def _(demo_mod, make_chapter_result, no_retry_ok, with_retry_ok):
    # ⑥ 对拍断言 + 结构化 chapter_result(r1114: details 含 expected 前缀键)
    passed = bool(no_retry_ok and with_retry_ok)
    summary = "no_retry_ok={} with_retry_ok={}".format(no_retry_ok, with_retry_ok)

    # 对拍期望(教学 payload;headless 可经 details["expected"] 键定位)
    expected = {
        "no_retry_ok": bool(no_retry_ok),
        "with_retry_ok": bool(with_retry_ok),
        "retry_call_count": demo_mod.get_call_count(),
    }
    print("expected:", expected)

    chapter_result = make_chapter_result(
        passed=passed,
        summary=summary,
        details={
            "expected": expected,
            "call_count": demo_mod.get_call_count(),
        },
    )
    return chapter_result, passed, summary


@app.cell(hide_code=True)
def _(chapter_result, mo):
    ok = chapter_result["passed"]
    mo.callout(mo.md("## {}: {}".format("✅ PASS" if ok else "❌ FAIL", chapter_result["summary"])), kind="success" if ok else "danger")
    return


@app.cell(hide_code=True)
def _(chapter_result, mo):
    from scalim_misc.notebook_support.results_view import details_to_rows

    d_rows = details_to_rows(chapter_result["details"])
    if d_rows:
        mo.ui.table(d_rows, selection=None)
    return


def run_chapter():
    """SSOT 入口：headless runner / pytest 通过此函数执行对拍。"""
    outputs, defs = app.run()
    return defs["chapter_result"]


if __name__ == "__main__":
    app.run()
