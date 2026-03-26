## ADDED Requirements

### Requirement: 用户可感知错误 MUST 具备稳定错误码
系统 MUST 为“用户可感知错误”(配置错误/输入不合法/运行期护栏违规等)提供稳定的字符串错误码 `code`.
该 `code` MUST 可用于测试断言与文档引用,且在同一主版本内保持稳定。

#### Scenario: raise a config error with stable code
- **WHEN** 用户提供非法配置导致校验失败
- **THEN** 系统抛出的异常 MUST 携带稳定的 `code`
- **AND** 该 `code` MUST 能用于测试断言而不依赖完整 message

### Requirement: 用户可感知错误 MUST 提供安全且可诊断的 message 与可选 hint/context
系统 MUST 为用户可感知错误提供:
- `message`: 人类可读的主错误信息(必填)
- `hint`: 可选的修复/迁移建议(可为空)
- `context`: 可选的结构化字段(用于诊断;默认仅包含安全字段)

#### Scenario: error includes hint and safe context
- **WHEN** 系统发现用户使用已移除/不可用的能力或参数
- **THEN** 错误 MUST 提供 `hint` 指向替代用法或迁移方向
- **AND** 若提供 `context`,其字段 MUST 可用于定位问题(例如 path/source_id/field_id),且不包含敏感值

### Requirement: 错误 message/context MUST 默认不泄露敏感信息
系统 MUST 将错误信息视为潜在外泄面,默认不得在 message/context 中泄露敏感信息,包括但不限于:
token/密钥、原始 SQL、URL query、绝对路径、用户数据明文、完整 loader 返回值等。
当需要提供可诊断信息时,系统 SHOULD 使用摘要/哈希/统计信息或红acted 字段代替原始值。

#### Scenario: sensitive value is redacted
- **GIVEN** 某异常 message/context 中可能包含敏感片段
- **WHEN** 系统将其作为用户可感知错误对外呈现
- **THEN** 输出 MUST 不包含敏感值原文
- **AND** 输出 MUST 仍可诊断(例如包含字段名/路径/错误码)

### Requirement: 系统 MUST 为测试提供稳定的错误断言点
系统 MUST 为用户可感知错误提供稳定断言点,至少包括 `code`(以及必要时的少量稳定字段),以避免测试依赖完整 message 文本导致脆弱。

#### Scenario: tests assert code not message
- **WHEN** 测试覆盖某个用户可感知错误分支
- **THEN** 断言 SHOULD 以 `code` 为主
- **AND** message 断言仅保留关键子串(如必须),不得绑定完整长消息
