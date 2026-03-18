## ADDED Requirements

### Requirement: compute sandbox rejection MUST include an actionable `call_by` migration hint
当 `compute` 表达式因安全沙箱限制被拒绝（例如出现 method call / attribute call）时，系统 MUST 在校验错误信息中提供可操作的迁移提示：
- 错误 MUST 明确指出：`compute` 不支持方法调用/attribute call
- 错误 MUST 建议使用 `call_by` 将复杂逻辑迁移到 Python 函数（并提示该能力受 allowlist 约束）
- 错误 SHOULD 提供最小可复制示例片段（例如 `call_by: ".helpers:fn(x=x)"`），以降低试错成本

#### Scenario: dict.get method call is rejected with a call_by hint
- **WHEN** 用户配置 `compute: "quick_pay_result.get('is_should_quick', False)"`
- **THEN** 校验 MUST 失败
- **AND** 错误信息 MUST 包含“method call/attribute call 不被允许”的明确原因
- **AND** 错误信息 MUST 包含 “use call_by” 的迁移提示

