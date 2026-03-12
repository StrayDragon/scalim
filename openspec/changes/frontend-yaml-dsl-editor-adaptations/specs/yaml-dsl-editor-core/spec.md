## MODIFIED Requirements

### Requirement: 导入/导出与模板新建

系统 MUST 支持从本地导入/导出 YAML,并提供“从模板新建”的起步体验(最小可运行配置 + 常见完整示例骨架)。

#### Scenario: 从模板新建生成 `outputs` 最小配置
- **WHEN** 用户选择“新建(最小模板)”
- **THEN** 系统 MUST 生成包含 `name`、`main_source` 与 `outputs` 的最小 YAML
- **AND** 该 YAML MUST 不包含旧顶层键 `output`
- **AND** 该 YAML MUST 可通过 canonical schema 的 schema-only 校验

### Requirement: Outline 与快速导航

系统 MUST 提供对 YAML DSL 结构的 outline,并支持点击导航到对应 YAML 文本位置。

#### Scenario: outline 展示并可定位 `outputs`
- **GIVEN** YAML 顶层包含 `outputs`
- **WHEN** 用户在 outline 中点击 `outputs`
- **THEN** 系统 MUST 将视图定位到 YAML 中对应的 `outputs` 块

## ADDED Requirements

### Requirement: 可选多 schema 选择(demand vs workflow)

系统 MUST 支持对当前文档选择并应用 schema,至少覆盖 demand 与 workflow 两类 YAML,并让补全/hover/校验与 issue 定位复用同一套 UI 模型。

#### Scenario: workflow YAML 使用 workflow schema 校验
- **GIVEN** 用户打开一份 workflow YAML 文本
- **WHEN** 用户选择 workflow schema(或系统根据文件类型自动选择)
- **THEN** 系统 MUST 使用 workflow schema 提供 schema-only 校验与 hover
