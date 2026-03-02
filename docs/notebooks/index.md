# Notebooks(marimo)

本页收录会在 GitHub Pages 上展示的 `marimo` 笔记本(构建时导出为静态 HTML).

## 列表

- `demo_big_data_report/demo_tutor`:核心能力导览(IR / Planning / Execution / Sinks / Observability / Guardrails)
  - 打开:[`demo_tutor.html`](demo_big_data_report/demo_tutor.html)

## 本地导出

```bash
just docs-export-notebooks
```

> 说明:导出的 HTML 会写入 `docs/notebooks/`,构建时会被打包进站点,但不会提交到 Git(已在 `.gitignore` 忽略).
