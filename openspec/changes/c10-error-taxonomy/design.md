## Context

scalim 当前存在大量分散的错误/异常类型与抛错风格:
- 一部分路径直接抛 `ValueError`/`TypeError`/`RuntimeError` 等内置异常,消息格式与信息密度不一致。
- 一部分模块定义了局部的自定义异常(例如 workflow/guardrails/dsl parsing),但缺少统一的“异常根类型 / 分类层级 / message/诊断字段”契约。
- 规范层面虽然对“错误信息必须可诊断/不得泄露敏感信息”等有零散约束,但缺少统一的可复用标准,导致错误口径与测试断言容易漂移。

本变更目标是先把“异常体系”规范化为一个可测试、可渐进迁移的 SSOT,再按任务逐步落地到各模块。

## Goals / Non-Goals

**Goals:**
- 建立严格树形的异常类型体系,且仅允许一个根: `ScalimException(Exception)`(用户可最终 fallback 捕获根异常)。
- 以异常类型(而非错误码)作为稳定程序契约:用户/测试通过 `isinstance`/`except` 进行分类处理与治理。
- 规定异常命名约定与分类分层(例如 YAML/Execution/Workflow 等大类),便于规模化治理与渐进迁移。
- 规定错误 message 的敏感信息治理原则(默认不泄露),以及测试口径(优先断言异常类型/字段;若必须断言 message 则以常量共享)。
- 给出可执行的迁移路径与验收口径(哪些错误点必须迁移、如何逐步替换既有异常、如何更新测试断言)。

**Non-Goals:**
- 不在本 change 中完成全仓库错误点的全面重构(本 change 产出规范/任务,实现按后续任务逐步推进)。
- 不强制一次性替换所有内置异常为自定义异常(允许阶段性并存,但新增/改动路径优先使用新体系)。
- 不引入错误码体系/错误码命名空间治理;也不引入与事件系统的额外映射层。
- 不改变既有业务行为(除错误呈现更清晰/更一致外),也不引入新的外部依赖。

## Decisions

### 1) 仅一个根: `ScalimException(Exception)`
**Decision:** 定义 `ScalimException(Exception)` 作为 scalim 所有自定义异常的根.仓库内新增的 scalim 自定义异常 MUST 直接或间接继承该根,并保持单继承以保证严格树形结构。

异常命名约定:
- 异常类名 MUST 以 `Scalim` 前缀开头(例如 `ScalimYamlException`),以避免跨模块命名冲突并提升可搜索性/可治理性。
- 异常类名 SHOULD 以 `Error`/`Exception` 结尾,或以明确的“可恢复”后缀结尾(例如 `*Recoverable*`/`*Retryable*`,按落地阶段统一)。
- 子类分层用于表达分类边界(例如 YAML/Execution/Workflow 等),用于治理与 `isinstance` 判断。

**Why:** 用户可通过 `except ScalimException:` 兜底处理全部 scalim 异常;同时仍可按子类进行精细化处理,不需要额外的错误码体系。

### 2) 稳定契约是“异常类型”,而非错误码
**Decision:** 不引入/不依赖稳定错误码.异常分类与治理通过异常类型层级表达;用户/测试通过 `isinstance`/`except` 进行分支判断。

**Why:** 类型继承体系天然提供了可扩展的“命名空间/分层治理/兜底边界”,且无需维护额外的 `code -> meaning` 映射表。

**Alternatives considered:**
- 字符串错误码:需要额外的治理与映射维护,并容易与类型体系重复。
- Enum 错误码:会引入导入/序列化/兼容性负担,对外仍需转字符串。

### 3) 与 Observer/Hook 错误事件不建立额外映射
**Decision:** 错误事件继续以异常对象/异常类型为中心表达,不引入“错误码 -> 事件字段集”的统一映射层。事件系统可继续输出 `type(error).__name__` 与安全的 `str(error)` 作为最小诊断信息。

**Why:** 事件系统已有 `error_type`/`error_message` 等字段,类型继承已经提供了足够的分类能力。

### 4) message 仅做人类诊断:如测试必须依赖,以常量共享
**Decision:** message 主要用于人类诊断,不作为稳定契约.若某些路径的测试必须断言 message(或其稳定子串),则该字符串 MUST 在实现侧以常量形式定义并在测试中复用,避免漂移。

**Why:** message 易随文案优化而变化;通过常量共享可降低维护成本,同时避免测试绑定完整长文本。

### 5) 迁移策略采用“新增优先 + 关键路径优先”的渐进方式
**Decision:** 迁移分阶段推进:
1) 新增/重构代码路径必须使用新异常体系(以减少新增债务)。
2) 关键入口与高频报错路径优先迁移(例如 YAML config 校验、execution 参数校验、guardrails fail-fast)。
3) 存量分散错误按模块逐步迁移,并允许在过渡期保留内置异常,但需要补充稳定的迁移提示与测试口径。

**Why:** 全量一次性替换风险过高;渐进迁移可控且可持续。

## Risks / Trade-offs

- [迁移成本与局部不一致] 过渡期会并存多种异常类型 → 缓解:明确“新增必须用新体系”,并提供优先级迁移清单与验收门禁(例如关键模块必须迁移)。
- [信息泄露风险] 更结构化的诊断字段/事件 payload 可能携带敏感数据 → 缓解:规范层强制默认 redaction,并要求错误 message/诊断字段 与错误事件输出均遵循“不泄露敏感值”的原则。
- [测试断言调整] 现有测试可能依赖 message → 缓解:优先断言异常类型/属性;如必须断言 message,使用常量共享与稳定子串。

## Migration Plan

- 规范 SSOT(本 change 的 delta spec): `openspec/changes/c10-error-taxonomy/specs/error-taxonomy/spec.md`。
- 后续若需要同步到主 specs: 使用 OpenSpec sync 流程写入 `openspec/specs/error-taxonomy/spec.md`。
- 文档治理边界:
  - 不直接编辑任何包含 `.gen.` 的文件。
  - 不编辑任何 `<!-- BEGIN AUTOGEN:<id> -->` / `<!-- END AUTOGEN:<id> -->` 注入区块内部。
  - 若需要对外文档化,优先在 OpenSpec specs 完成,并用 `just gen-docs` 同步生成页/注入区块(由 `just qa`/CI drift gate 兜底)。

## Resolved Questions

- 错误码命名空间如何分层(例如 `yaml.*`/`execution.*`/`workflow.*`)以便规模化治理?
  - **Answer:** 不引入错误码.规模化治理通过异常类型树完成: `ScalimException` 作为唯一根,在其下按域划分子树(例如 YAML/Execution/Workflow),用户通过 `isinstance`/`except` 进行分类处理。
- 结构化错误是否需要与现有事件系统(Observer/Hook 错误事件)建立统一映射字段集?
  - **Answer:** 不需要.类型继承体系即可,不新增错误码/映射等冗余组织.若单元测试需要依赖报错提示文字,则提示文字 MUST 以常量共享,避免不一致导致维护成本过高。
