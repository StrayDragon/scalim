## MODIFIED Requirements

### Requirement: template_vars enables LiteJinja2 precompile before YAML parse
系统 MUST 支持在读取 demand/workflow YAML 文本后、YAML parse 前执行 LiteJinja2 预编译,以便调用方通过 `template_vars` 注入 `{{ x }}`/`{% ... %}` 模板值.

当且仅当调用方显式提供 `template_vars`(非 `None`)时,系统 MUST 启用该预编译步骤;未提供时 MUST 不进行模板渲染(保持原有语义与安全边界).

#### Scenario: demand YAML supports unquoted placeholders
- **GIVEN** demand YAML 文本包含 `outputs.0.container.path: {{ output_path }}` 形式的未加引号占位符
- **WHEN** 调用方执行 `compile(..., options=RunOptions(..., template_vars={"output_path": "./output/report.xlsx"}))`
- **THEN** 系统 MUST 先完成模板渲染再进行 YAML parse
- **AND** YAML parse MUST 成功
- **AND** 编译后的输出路径 MUST 等于 `"./output/report.xlsx"`

#### Scenario: workflow YAML fields can be templated
- **GIVEN** workflow YAML 文本包含 `workflow.options.max_concurrency: {{ max_concurrency }}`
- **WHEN** 调用方执行 `run_workflow(..., options=RunOptions(..., template_vars={"max_concurrency": 3}))`
- **THEN** workflow 配置加载 MUST 先完成模板渲染再进行 YAML parse
- **AND** 编译后的 `max_concurrency` MUST 等于 `3`
