# framework-logging Specification

**状态: ✅ 已实现**
## Purpose
为框架内部日志建立统一的 Python 标准库 `logging` 使用约定,以保证默认静默、命名空间稳定、输出前缀一致,并提供可扩展的诊断字段与 context 绑定机制。

## Context
框架内部存在多类“面向运行期诊断”的日志输出点(例如可选依赖不可用提示、资源护栏告警、性能阈值告警)。如果这些输出在前缀/字段/文案上不一致,下游在排障与监控上会面临:

- 难以 grep 与聚合(同类问题不同格式).
- 难以做稳定告警(依赖字符串匹配易漂移).
- 默认环境出现库侧噪音(无 handler 时的 `logging` 警告或重复提示).

因此需要一套跨模块可复用的最小约定,并遵循库代码惯例: 不为下游做全局 `logging` 配置决定。

## Related Concepts
- 统一日志工具模块 (`loggingx`)
- 运行时配置校验器 (`config_parsing/validator`)
- 派生输出护栏模块 (`output_composition`)
- 性能观测模块 (`ob/presets/performance`)

## Requirements
### Requirement: 框架内部日志使用标准库 `logging` 且默认静默
系统 MUST 使用 Python 标准库 `logging` 输出框架内部日志,并遵循库代码“默认静默”约束。

- 系统 MUST NOT 在运行时调用 `logging.basicConfig(...)` 或修改 `root logger`。
- 系统 MUST 在导入内部日志工具后,为 `logging.getLogger("scalim")` 安装 `logging.NullHandler`,以避免无 handler 时的库侧噪音。

#### Scenario: `scalim` logger 默认带 `NullHandler`
- **WHEN** 下游未显式配置 `logging` 且导入 `scalim._internal.loggingx`
- **THEN** `logging.getLogger("scalim")` MUST 至少包含一个 `NullHandler`

### Requirement: 统一 logger 命名空间为 `scalim`/`scalim.<subsystem>`
系统 MUST 将框架内部日志统一归入 `scalim` 命名空间,并允许按子系统拆分。

- 当 subsystem 为空时,logger 名 MUST 为 `scalim`。
- 当 subsystem 非空时,logger 名 MUST 为 `scalim.<subsystem>`。

#### Scenario: `schema` 子系统 logger 名稳定
- **WHEN** 请求 `schema` 子系统 logger
- **THEN** logger.name MUST 为 `scalim.schema`

### Requirement: 用户可见日志 message 统一前缀 `[scalim] <subsystem>:`
系统 MUST 在用户可见的框架内部日志 message 中包含稳定前缀,且该前缀不依赖下游 `formatter` 才可见。

- 当 subsystem 非空时,前缀 MUST 为 `[scalim] <subsystem>: `。
- 当 subsystem 为空时,前缀 MUST 为 `[scalim] `。

#### Scenario: 性能阈值提示包含 `performance` 前缀
- **WHEN** 性能观测检测到 `memory_increase` 超过阈值
- **THEN** warning message MUST 包含 `[scalim] performance:` 且包含 `memory_increase_mb` 字段

### Requirement: runtime MUST NOT emit JSONSchema skip warnings
系统 MUST NOT 在 runtime 的 YAML parse/validate/compile/run 路径中输出“jsonschema 不可用/已跳过 schema 校验”的 warning。

如果需要执行 JSONSchema 校验,应通过工具链的 schema-only 入口完成（例如 CLI/LSP），而不是在 runtime 主线隐式尝试可选依赖。

#### Scenario: runtime does not log jsonschema-skip noise
- **GIVEN** 运行环境未安装 `jsonschema`(或依赖不兼容导致无法导入)
- **WHEN** 用户运行 runtime 入口解析一个在语义校验层面有效的 YAML DSL 配置
- **THEN** 输出 MUST NOT 包含任何提示 “已跳过 schema 校验” 或 “jsonschema 不可用” 的 warning message

### Requirement: 诊断字段追加采用稳定 `k=v` 约定,并提供 context 绑定机制
系统 MUST 在需要输出附加诊断字段时采用 `k=v, k2=v2` 的稳定追加格式,并提供上下文绑定机制以支持下游扩展。

- `k=v` 追加字段的 key MUST 按字典序稳定排序。
- value 为 `None` 的字段 MUST 被省略。
- 系统 MUST 支持基于 `logging.LoggerAdapter` 绑定上下文字段,以便下游 `formatter` 访问。

#### Scenario: `k=v` 排序且忽略 `None`
- **WHEN** 需要输出字段 `{b: 2, a: 1, skip: None}`
- **THEN** `k=v` 文本 MUST 为 `a=1, b=2`(顺序稳定)且不包含 `skip`

#### Scenario: context 绑定可向下游暴露字段
- **WHEN** 系统绑定上下文 `run_id="r1"`
- **THEN** 绑定后的 logger MUST 为 `LoggerAdapter` 且其 `extra` MUST 包含 `run_id`

### Requirement: runtime MUST NOT mix print with structured logging

系统 MUST 将 runtime 的用户可见诊断输出统一为结构化 logger 输出（例如 `loggingx` 的 prefix + kv）,并禁止在 runtime 代码路径中直接使用 `print(...)`.

#### Scenario: print usage in runtime fails fast
- **WHEN** 在 runtime 代码路径中出现 `print(...)`
- **THEN** gate MUST fail-fast 并提示迁移到结构化 logger
