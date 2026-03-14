## ADDED Requirements

### Requirement: docs-site 提供 `demo_big_data_report` 主线教程入口页
系统 MUST 在 `docs/doc/` 下提供一页可发现的“主线教程: demo_big_data_report”入口文档,用于串联:

- `marimo` 教程入口(`notebooks/marimo/demo_big_data_report/demo_main.py`)
- `just examples` 集成对拍入口(`notebooks/marimo/run_examples.py`)
- YAML DSL canonical example 的 SSOT 路径(`notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`)

该入口页 MUST 明确声明 doc governance 边界(哪些手工维护,哪些为 `*.gen.*`/注入区块,以及 `just gen-docs`/`just qa` 门禁)。

#### Scenario: 入口页存在且可发现
- **WHEN** 读者打开 `docs/doc/getting-started/reading-guide.md`
- **THEN** 文档中 MUST 存在指向该入口页的链接

#### Scenario: YAML DSL 使用方可发现入口页
- **WHEN** 读者打开 `docs/doc/yaml-dsl/index.md`
- **THEN** 文档中 MUST 存在指向该入口页的链接
