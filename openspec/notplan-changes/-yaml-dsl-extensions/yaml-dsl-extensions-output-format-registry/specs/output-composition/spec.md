## ADDED Requirements

### Requirement: composed outputs 使用可扩展的 format registry 创建 sinks
系统 SHALL 允许 composed outputs 通过 `format id → factory` registry 创建输出 sinks,以支持除内置 `csv/excel` 之外的扩展输出格式.

约束:
- 内置 `csv/excel` MUST 保持兼容且行为不变
- composed outputs 的 sinks MUST 为流式行式 sink(`IRowSink`),不满足时必须给出可行动错误

#### Scenario: 自定义 format id 在 composed outputs 中可用
- **GIVEN** 扩展注册 format id `parquet` 的 factory
- **AND** YAML `outputs[0].container.type: parquet` 且 `outputs[0].container.streaming: true`
- **WHEN** 运行编译与执行
- **THEN** composed outputs MUST 使用 registry 创建并使用该 sink 写出结果

#### Scenario: composed outputs 遇到非 row sink 时失败
- **GIVEN** 某 format factory 返回非 `IRowSink`
- **WHEN** composed outputs 尝试创建该目标 sink
- **THEN** 系统 MUST fail-fast 并提示 composed outputs 仅支持 row sinks

### Requirement: composed outputs 创建 sinks 时 MUST 透传 `container.options`
系统 MUST 将 YAML `outputs[*].container.options`(若存在)透传给 registry 的 format factory,以支持扩展格式的配置化行为.

#### Scenario: composed outputs 透传 options
- **GIVEN** YAML `outputs[0].container.type: parquet`
- **AND** YAML `outputs[0].container.options: {compression: zstd}`
- **WHEN** composed outputs 通过 registry 创建该目标 sink
- **THEN** factory MUST 能读取到 `options.compression == "zstd"`

### Requirement: composed outputs 支持容器型输出(handle)的资源复用
系统 SHALL 支持“容器型输出(handle)”在 composed outputs 中跨 target 复用底层资源(例如同一路径共享一个 workbook/sqlite 连接等).

约束:
- 复用 MUST 基于确定性的 `container_key`(至少包含 format_id + path + 相关 options 的稳定表示)
- 每个 handle MUST 在 composed outputs 生命周期结束时被正确 close

#### Scenario: 同一 container_key 复用单一 handle
- **GIVEN** composed outputs 中存在两个 targets,其 `format_id/path/options` 组合相同(因此 `container_key` 相同)
- **AND** 对应 format factory 为容器型输出并创建 handle
- **WHEN** composed outputs 装配 sinks
- **THEN** 系统 MUST 仅创建一次 handle 并从该 handle 派生多个 target sinks
- **AND** composed outputs 生命周期结束时 MUST close 该 handle

### Requirement: 单输出与 composed outputs 共享同一套 format registry
系统 MUST 使单输出模式(ExecutionRequest.output)与 composed outputs(ExecutionRequest.output_composition)共享同一套 format registry,避免“单输出支持某格式但 composed outputs 不支持(或反之)”的漂移.

#### Scenario: registry 在两种模式下行为一致
- **GIVEN** 扩展注册 format id `jsonl`
- **WHEN** 用户分别以单输出模式与 composed outputs 模式使用 `jsonl`
- **THEN** 两种模式 MUST 通过同一 registry 路由到相同 factory(并遵循各自模式的约束)
