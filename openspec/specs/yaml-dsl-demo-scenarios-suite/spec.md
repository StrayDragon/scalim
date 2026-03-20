# yaml-dsl-demo-scenarios-suite Specification

## Purpose
TBD - created by archiving change c16-demo-big-data-report-yaml-mainline. Update Purpose after archive.
## Requirements
### Requirement: YAML DSL 场景库必须覆盖电商/广告/客服三类域
系统 MUST 在 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/` 下维护一个 YAML DSL 场景库（fixtures），第一版至少包含：

- 电商（ecommerce）：以 canonical demand YAML 为核心（路径由其它规范约束保持稳定）
- 广告（ads）：至少 1 份 demand YAML（可选 workflow）
- 客服（support）：至少 1 份 demand YAML（可选 workflow）

场景库的 YAML MUST 以最新 schema 为基准编写，并在文件头部包含 YAML LSP schema modeline。

#### Scenario: ads/support 场景 YAML 存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ads/` 与 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/support/`
- **THEN** 每个目录 MUST 至少存在 1 个 `*.yaml` demand 文件

### Requirement: 场景库 YAML 必须纳入 examples gate 并通过校验
系统 MUST 将场景库 YAML 纳入 `just examples` 的确定性回归范围，并满足：

- demand YAML：`PROJECT_CLI_NAME yaml-dsl validate <file>` 通过
- workflow YAML：仅允许 schema-only 校验（显式指定 workflow schema 路径）通过

#### Scenario: 场景库 YAML 在 gate 中可校验通过
- **WHEN** 开发者运行 `just examples`
- **THEN** runner MUST 执行对场景库 YAML 的校验/运行对拍
- **AND** 所有场景 MUST 通过并输出可定位的 summary

### Requirement: capability coverage matrix 必须可审计并以 schema 为准
系统 MUST 提供一个可检查的 capability coverage matrix 文件，用于将最新 schema 的关键能力点映射到：

- 覆盖该能力点的 YAML 文件路径
- 覆盖该能力点的章节/对拍断言入口

该矩阵 MUST 以 `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与 `workflow.gen.json` 为唯一基准。

#### Scenario: coverage matrix 文件存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/`
- **THEN** MUST 存在一份 coverage matrix 文件且内容可读

