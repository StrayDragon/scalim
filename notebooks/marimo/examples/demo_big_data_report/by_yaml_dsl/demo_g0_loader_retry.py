import marimo

__generated_with = "0.19.9"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # YAML DSL: loader retry demo

        目标:构造一个会在第一次调用失败、第二次成功的 loader,并做“对拍验证”:

        - 不启用 retry:执行失败(符合预期)
        - 启用 retry:自动重试后执行成功(符合预期)

        本示例展示:
        - `_templates.retry.*` + YAML anchor/merge 的复用写法
        - driver 注入 `should_retry(exc, ctx)`(避免在 YAML 中重复写回调引用)
        """
    )
    return


@app.cell
def _():
    import tempfile
    import textwrap
    from pathlib import Path

    from scalim.dsl.by_yaml import run
    from scalim.execution.loader_retry import LoaderRetryPoliciesSpec, LoaderRetryPolicySpec
    from scalim.sinks.sink_memory import InMemoryRowSink

    import _loader_retry_demo_mod as demo_mod

    # 说明:`marimo` 的脚本运行器会对 `cell` 代码做去缩进处理.
    # 为避免多行字符串里的 YAML 缩进被破坏,这里统一用 `textwrap.dedent` 生成.
    yaml_no_retry = textwrap.dedent(
        """
        name: loader_retry_demo

        main_source:
          source_id: orders
          loader: "_loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              field: order_id
        """
    ).lstrip()

    yaml_with_retry = textwrap.dedent(
        """
        name: loader_retry_demo

        _templates:
          retry:
            transient_default: &transient_default
              enabled: true
              max_attempts: 5
              max_elapsed_seconds: 5.0
              backoff: fixed
              base_delay_seconds: 0.0
              max_delay_seconds: 0.0
              jitter: false

        retry:
          <<: *transient_default
          # 只需要一次重试(第 2 次调用成功)
          max_attempts: 2

        main_source:
          source_id: orders
          loader: "_loader_retry_demo_mod:load_orders"
          fields:
            order_id:
              field: order_id
        """
    ).lstrip()

    allowed_modules = frozenset(["_loader_retry_demo_mod"])

    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_no_retry_path = Path(tmpdir) / "no_retry.yaml"
        yaml_no_retry_path.write_text(yaml_no_retry, encoding="utf-8")

        yaml_with_retry_path = Path(tmpdir) / "with_retry.yaml"
        yaml_with_retry_path.write_text(yaml_with_retry, encoding="utf-8")

        # 对拍 1: 不启用 `retry` -> 第一次失败直接抛错
        demo_mod.reset()
        sink_no_retry = InMemoryRowSink()
        try:
            _ = run(
                str(yaml_no_retry_path),
                allowed_modules=allowed_modules,
                sink=sink_no_retry,
            )
        except demo_mod.TransientError as e:
            print("✅ 未启用 `retry`(预期失败):", e)
        else:
            msg = "未启用 `retry` 时应抛出 TransientError,但 `run()` 却成功执行"
            raise AssertionError(msg)

        # 对拍 2: 启用 `retry` + `driver` 注入 `should_retry` -> 自动重试后成功
        demo_mod.reset()
        sink_with_retry = InMemoryRowSink()
        injected_retry = LoaderRetryPoliciesSpec(default=LoaderRetryPolicySpec(should_retry=demo_mod.should_retry))
        result = run(
            str(yaml_with_retry_path),
            allowed_modules=allowed_modules,
            sink=sink_with_retry,
            loader_retry=injected_retry,
        )

        _ = result
        assert sink_with_retry.get_data() == [{"order_id": 1}]
        assert demo_mod.get_call_count() == 2
        print("✅ 启用 `retry`(预期成功): 行数据=", sink_with_retry.get_data(), "调用次数=", demo_mod.get_call_count())
    return


if __name__ == "__main__":
    app.run()
