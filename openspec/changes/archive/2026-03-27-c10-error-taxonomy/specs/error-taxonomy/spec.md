## ADDED Requirements

### Requirement: scalim MUST 暴露单根异常类型
系统 MUST 定义 `ScalimException(Exception)` 作为 scalim 内所有自定义异常的根。
仓库内新增的 scalim 自定义异常 MUST 直接或间接继承 `ScalimException`，并 SHOULD 使用单继承以保持严格树形结构。

#### Scenario: user catches scalim root exception
- **WHEN** 用户希望兜底处理 scalim 抛出的全部自定义异常
- **THEN** `except ScalimException:` MUST 捕获到这些异常

### Requirement: scalim 自定义异常类名 MUST 以 `Scalim` 前缀开头
系统 MUST 为所有 scalim 自定义异常统一使用 `Scalim*` 的类名命名约定(包括分类基类与叶子异常),以避免跨模块命名冲突并提升可搜索性/可治理性.

#### Scenario: exception class name has Scalim prefix
- **WHEN** 任意 scalim 自定义异常对外暴露
- **THEN** 其异常类名 MUST 以 `Scalim` 开头(例如 `ScalimYamlException`)

### Requirement: 用户可感知错误 MUST 以异常类型作为稳定契约
系统 MUST 为常见用户可感知错误提供清晰的异常类型层级(例如 YAML/Execution/Workflow 维度的基类与叶子类)。
用户/测试 SHOULD 优先使用 `isinstance`/`except` 进行分支判断，而不是依赖 message 文本或额外的错误码映射。

#### Scenario: tests assert exception type
- **WHEN** 测试覆盖某个用户可感知错误分支
- **THEN** 测试 SHOULD 断言异常类型(以及必要的显式字段/属性)
- **AND** message 断言仅保留关键子串(如必须),不得绑定完整长消息

### Requirement: 错误 message/诊断字段 MUST 默认不泄露敏感信息
系统 MUST 将错误信息视为潜在外泄面,默认不得在 message/诊断字段中泄露敏感信息,包括但不限于:
token/密钥、原始 SQL、URL query、绝对路径、用户数据明文、完整 loader 返回值等。
当需要提供可诊断信息时,系统 SHOULD 使用摘要/哈希/统计信息或红acted 字段代替原始值。

#### Scenario: sensitive value is redacted
- **GIVEN** 某异常 message/诊断字段中可能包含敏感片段
- **WHEN** 系统将其作为用户可感知错误对外呈现
- **THEN** 输出 MUST 不包含敏感值原文
- **AND** 输出 MUST 仍可诊断(例如包含字段名/路径/异常类型)

### Requirement: 若测试必须断言 message, MUST 以常量共享
系统 MUST 将任何会被测试断言的 message/模板以常量形式集中定义并共享,避免测试与实现不一致导致维护成本过高。

#### Scenario: shared message constant
- **GIVEN** 某条异常 message 会被多个测试断言
- **WHEN** 实现侧需要调整该 message 文案
- **THEN** 仅需更新常量,测试可通过复用常量避免逐处手工同步

### Requirement: Observer/Hook 错误事件 MUST 输出异常类型与安全消息
系统在触发 `on_error` 等错误事件时,事件 payload MUST 至少包含:
- `error_type`: `type(error).__name__`
- `error_message`: 安全的 `str(error)`(不得泄露敏感信息)

#### Scenario: error event includes type and safe message
- **WHEN** workflow/execution 触发错误事件
- **THEN** 事件 MUST 可提供可诊断的 `error_type`
- **AND** `error_message` MUST 遵循敏感信息治理(不输出敏感值原文)
