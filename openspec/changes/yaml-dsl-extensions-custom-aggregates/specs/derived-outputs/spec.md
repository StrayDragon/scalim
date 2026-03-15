## ADDED Requirements

### Requirement: 支持从 YAML extensions 装配自定义派生聚合器
系统 SHALL 允许通过 YAML `extensions` 注册/引用自定义派生聚合器,并在 `outputs[*].aggregate` 中使用,以生成派生输出.

约束:
- 自定义聚合器 MUST 提供 `IDerivedAggregationSpec`(或等价接口),并可构建 `IRowAggregator`
- 自定义聚合器 MUST 同时提供派生输出的 `output_field_ids`,用于构造派生输出的 `ExportLayout`

#### Scenario: 自定义聚合器产生派生输出行
- **GIVEN** YAML outputs 中某目标启用自定义 aggregate
- **WHEN** 执行结束并触发 derived finalize
- **THEN** 系统 MUST 将聚合器输出行写入该派生输出目标

### Requirement: 自定义聚合器的并发边界必须可校验并 fail-fast
系统 MUST 在运行开始前(或装配阶段)调用自定义聚合器的并发校验逻辑,以确保 `parallel_mode` 下的结果确定性边界明确.

#### Scenario: 自定义聚合器不支持 adaptive 时 fail-fast
- **GIVEN** 自定义聚合器声明/校验不支持 `parallel_mode="adaptive"`
- **WHEN** 用户以 `parallel_mode="adaptive"` 运行
- **THEN** 系统 MUST fail-fast 并提示切换到 `parallel_mode="seq"` 或更换聚合器实现
