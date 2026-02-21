# marimo examples

本目录收录 `scalim` 的 **marimo** 示例（单文件 notebook + 配套辅助模块）。

## demos

- `demo_big_data_report/demo_tutor.py`：一个“从零理解 scalim 运行时”的导览 notebook（IR / Planning / Execution / Sinks / Observability / Guardrails）。

## 运行方式

交互式打开：

```bash
uv run marimo edit notebooks/marimo/examples/demo_big_data_report/demo_tutor.py
```

导出为静态 HTML（用于 GitHub Pages 展示）：

```bash
uv run marimo export html notebooks/marimo/examples/demo_big_data_report/demo_tutor.py -o /tmp/demo_tutor.html --no-include-code
```

