# language: zh-CN
# capability: execution-error-taxonomy
# purpose: 为 scalim 建立统一的异常体系规范:以 ScalimError 作为唯一根,并在其下按域拆分子类;对用户可感知错误以异常类型/显式字段作为稳定契约;同时约束错误事件的最小输出与敏感信息治理,并提供可执行的测试断言口径. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-error-taxonomy

  @req:r37 @human
  场景: scalim MUST 暴露单根异常类型
    - 系统 MUST 定义 `ScalimError(Exception)` 作为 scalim 内所有自定义异常的根。 仓库内新增的 scalim 自定义异常 MUST 直接或间接继承 `ScalimError`，并 SHOULD 使用单继承以保持严格树形结构。

  @req:r281 @human
  场景: scalim 自定义异常类名 MUST 以 `Scalim` 前缀开头
    - 系统 MUST 为所有 scalim 自定义异常统一使用 `Scalim*` 的类名命名约定(包括分类基类与叶子异常),以避免跨模块命名冲突并提升可搜索性/可治理性.

  @req:r405 @human
  场景: 用户可感知错误 MUST 以异常类型作为稳定契约
    - 系统 MUST 为常见用户可感知错误提供清晰的异常类型层级(例如 YAML/Execution/Workflow 维度的基类与叶子类)。 用户/测试 SHOULD 优先使用 `isinstance`/`except` 进行分支判断，而不是依赖 message 文本或额外的错误码映射。

  @req:r500 @human
  场景: 错误 message/诊断字段 MUST 默认不泄露敏感信息
    - 系统 MUST 将错误信息视为潜在外泄面,默认不得在 message/诊断字段中泄露敏感信息,包括但不限于: token/密钥、原始 SQL、URL query、绝对路径、用户数据明文、完整 loader 返回值等。 当需要提供可诊断信息时,系统 SHOULD 使用摘要/哈希/统计信息或红acted 字段代替原始值。

  @req:r578 @human
  场景: 若测试必须断言 message, MUST 以常量共享
    - 系统 MUST 将任何会被测试断言的 message/模板以常量形式集中定义并共享,避免测试与实现不一致导致维护成本过高。

  @req:r638 @human
  场景: Observer/Hook 错误事件 MUST 输出异常类型与安全消息
    - 系统在触发 `on_error` 等错误事件时,事件 payload MUST 至少包含: - `error_type`: `type(error).__name__` - `error_message`: 安全的 `str(error)`(不得泄露敏感信息)

  @req:r684 @human
  场景: public-facing error messages MUST be formatted by a single policy
    - 系统 MUST 提供单点“异常 → 对外消息”格式化策略（默认 redacted,显式 debug 才 full）,并要求所有对外出口统一使用该策略（CLI JSON、viz bundle、workflow report、events error payload 等）.

  @req:r724 @human
  场景: duplicated error type names MUST be eliminated
    - 系统 MUST 禁止同名异常类型在多个模块重复定义（例如 workflow config error）,以避免语义混淆与捕获不一致.

  @req:r756 @human
  场景: 核心模块内 `raise ... from` 异常链规范
    - 在 scalim 核心模块中，将捕获的异常重新包装为另一异常时，默认 MUST 使用 `from exc`（或等价的显式 cause）以保留异常链与根因诊断信息。 仅在公共 API 边界且显式需要向调用方隐藏第三方或内部实现细节时 MAY 使用 `from None`；每一处 `from None` MUST 附带相邻注释说明抑制链的原因与适用边界（例如 YAML 解析边界隐藏解析器内部栈）。 内部配置/编译路径（例如将 `ValueError` / `TypeError` 包装为 `ScalimWorkflowConfigError`）MUST 使用 `from exc`，除非该路径属于上述已文档化的 API 边界例外。
  @req:r37 @human
  场景: user-catches-scalim-root-exception
    - 必须成立：当 用户希望兜底处理 scalim 抛出的全部自定义异常；那么 `except ScalimError:` MUST 捕获到这些异常
    当 用户希望兜底处理 scalim 抛出的全部自定义异常
    那么 `except ScalimError:` MUST 捕获到这些异常
  @req:r281 @human
  场景: exception-class-name-has-scalim-prefix
    - 必须成立：当 任意 scalim 自定义异常对外暴露；那么 其异常类名 MUST 以 `Scalim` 开头(例如 `ScalimYamlError`)
    当 任意 scalim 自定义异常对外暴露
    那么 其异常类名 MUST 以 `Scalim` 开头(例如 `ScalimYamlError`)
  @req:r405 @human
  场景: tests-assert-exception-type
    - 必须成立：当 测试覆盖某个用户可感知错误分支；那么 测试 SHOULD 断言异常类型(以及必要的显式字段/属性)
    当 测试覆盖某个用户可感知错误分支
    那么 测试 SHOULD 断言异常类型(以及必要的显式字段/属性)
  @req:r500 @human
  场景: sensitive-value-is-redacted
    - 必须成立：假如 某异常 message/诊断字段中可能包含敏感片段；当 系统将其作为用户可感知错误对外呈现；那么 输出 MUST 不包含敏感值原文
    假如 某异常 message/诊断字段中可能包含敏感片段
    当 系统将其作为用户可感知错误对外呈现
    那么 输出 MUST 不包含敏感值原文
  @req:r578 @human
  场景: shared-message-constant
    - 必须成立：假如 某条异常 message 会被多个测试断言；当 实现侧需要调整该 message 文案；那么 仅需更新常量,测试可通过复用常量避免逐处手工同步
    假如 某条异常 message 会被多个测试断言
    当 实现侧需要调整该 message 文案
    那么 仅需更新常量,测试可通过复用常量避免逐处手工同步
  @req:r638 @human
  场景: error-event-includes-type-and-safe-message
    - 必须成立：当 workflow/execution 触发错误事件；那么 事件 MUST 可提供可诊断的 `error_type`
    当 workflow/execution 触发错误事件
    那么 事件 MUST 可提供可诊断的 `error_type`
  @req:r684 @human
  场景: the-same-exception-yields-consistent-external-messaging
    - 必须成立：当 同一异常在不同入口（CLI/Workflow/Viz）被呈现；那么 对外消息 MUST 遵循同一 redaction 策略且保持一致结构
    当 同一异常在不同入口（CLI/Workflow/Viz）被呈现
    那么 对外消息 MUST 遵循同一 redaction 策略且保持一致结构
  @req:r724 @human
  场景: a-single-canonical-workflow-config-error-type-exists
    - 必须成立：当 维护者检索 workflow config error 类型定义；那么 全库 MUST 仅存在一个 canonical 定义,其余入口仅做包装补充上下文
    当 维护者检索 workflow config error 类型定义
    那么 全库 MUST 仅存在一个 canonical 定义,其余入口仅做包装补充上下文
  @req:r756 @human
  场景: 内部错误包装保留链
    - 必须成立：假如 核心模块内捕获到异常；当 代码抛出包装后的领域异常；那么 `raise` MUST 使用 `from exc`
    假如 核心模块内捕获到异常
    当 代码抛出包装后的领域异常
    那么 `raise` MUST 使用 `from exc`

  @req:r756 @human
  场景: 允许的-from-none-具备理由
    - 必须成立：当 代码使用 `raise ... from None`；那么 相邻注释 MUST 说明为何在此边界抑制 cause 链
    当 代码使用 `raise ... from None`
    那么 相邻注释 MUST 说明为何在此边界抑制 cause 链
