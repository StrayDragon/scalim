# framework-logging (delta) Specification

## MODIFIED Requirements

### Requirement: 用户可见日志 message 统一前缀 `[scalim] <subsystem>:`
系统 MUST 在用户可见的框架内部日志 message 中包含稳定前缀,且该前缀不依赖下游 `formatter` 才可见。

- 当 subsystem 非空时,前缀 MUST 为 `[scalim] <subsystem>: `。
- 当 subsystem 为空时,前缀 MUST 为 `[scalim] `。

#### Scenario: 性能阈值提示包含 `performance` 前缀
- **WHEN** 性能观测检测到 `memory_increase` 超过阈值
- **THEN** warning message MUST 包含 `[scalim] performance:` 且包含 `memory_increase_mb` 字段

## ADDED Requirements

### Requirement: runtime MUST NOT emit JSONSchema skip warnings
系统 MUST NOT 在 runtime 的 YAML parse/validate/compile/run 路径中输出“jsonschema 不可用/已跳过 schema 校验”的 warning。

如果需要执行 JSONSchema 校验,应通过工具链的 schema-only 入口完成（例如 CLI/LSP），而不是在 runtime 主线隐式尝试可选依赖。

#### Scenario: runtime does not log jsonschema-skip noise
- **GIVEN** 运行环境未安装 `jsonschema`(或依赖不兼容导致无法导入)
- **WHEN** 用户运行 runtime 入口解析一个在语义校验层面有效的 YAML DSL 配置
- **THEN** 输出 MUST NOT 包含任何提示 “已跳过 schema 校验” 或 “jsonschema 不可用” 的 warning message

