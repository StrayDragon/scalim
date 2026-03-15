## ADDED Requirements

### Requirement: 支持 ANALYZE 扩展点(只读分析器)
系统 SHALL 支持 `extensions.analyze` 声明 analyzers,analyzer 通过 Python 引用加载并在显式启用扩展的情况下执行.

约束:
- analyzer MUST 为只读(不得修改 raw/config/IR/request 的最终语义);其输出仅用于诊断/建议/元信息
- analyzer 失败 MUST 产生可行动错误(包含 analyzer ref 与执行阶段),并允许配置 fail-fast 或降级为 warning

#### Scenario: analyzer 产出告警
- **GIVEN** YAML `extensions.analyze` 声明了一个 analyzer
- **WHEN** 用户在“启用扩展分析”的模式下运行编译/校验
- **THEN** 系统 MUST 将 analyzer 产出的 warning/errors 合并到校验结果中(可被 CLI/CI 消费)
