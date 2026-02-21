# scalim

Scalim 是一个 **Python-first** 的计算运行时：用 IR（中间表示）描述数据需求，构建执行计划并执行，输出到不同 sink，同时提供 hooks / observability / guardrails 等运行时能力。

本仓库只包含核心运行时与示例，不包含任何特定方言（例如 YAML DSL）或 CLI。需要方言/CLI 时建议在独立包中依赖 `scalim` 核心实现。

## 文档（统一入口）

完整文档请以 MkDocs 站点为准：

- 本地预览：`just docs-serve`
- 构建站点：`just docs-build`
- 部署到 GitHub Pages：见 `.github/workflows/cd.yaml`（并在 Settings → Pages 选择 “GitHub Actions”）

## Notebooks（marimo）

- 入口：`notebooks/marimo/examples/demo_big_data_report/demo_tutor.py`
- 交互式打开：`just notebook`
- 导出为文档站点可访问的静态 HTML：`just docs-export-notebooks`

## 开发

```bash
just qa
```

## License

Apache-2.0（见 `LICENSE`）。
