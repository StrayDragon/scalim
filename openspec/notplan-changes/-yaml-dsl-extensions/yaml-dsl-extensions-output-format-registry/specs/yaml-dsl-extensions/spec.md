## ADDED Requirements

### Requirement: 输出格式 registry 可扩展,并可被 YAML outputs 使用
系统 SHALL 允许扩展注册 `output format id → factory` 的映射,并允许 YAML `outputs[*].container.type` 使用自定义 format id.

约束:
- 内置 `workbook/csv` MUST 保持兼容
- `container.type: workbook` MUST 按现有语义创建 Excel/workbook 输出(实现侧可映射到 execution format_id `excel`)
- `container.type: csv` MUST 按现有语义创建 CSV 输出(映射到 execution format_id `csv`)
- 当 `container.type` 为非内置值时,系统 MUST 通过 registry 解析并创建输出端
- `container.options`(若存在) MUST 作为扩展配置传入 factory

#### Scenario: 自定义 format id 可用于 outputs
- **GIVEN** 扩展注册了 format id `parquet`
- **AND** YAML `outputs[0].container.type: parquet`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 通过 registry 创建该输出目标的 sink,并写出结果(或在 factory 不满足约束时给出可行动错误)

### Requirement: output format factory MUST 可接收 `container.options`
系统 MUST 将 YAML `outputs[*].container.options`(若存在)传递给对应的 output format factory,以支持扩展格式的自定义行为.

#### Scenario: options 透传给 factory
- **GIVEN** YAML `outputs[0].container.type: parquet`
- **AND** YAML `outputs[0].container.options: {compression: zstd}`
- **WHEN** 系统通过 registry 创建该输出 sink
- **THEN** factory MUST 能读取到 `options.compression == "zstd"`
