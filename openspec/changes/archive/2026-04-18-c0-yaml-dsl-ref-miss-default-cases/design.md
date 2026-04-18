## Context

当前执行模型中，`LoadRef`（relation lookup）在 miss 时会将字段写回为 `None`。下游为了把 `None` 变成 `0/""/False` 等“业务零值”，往往写大量 `_safe_*` 派生字段（`int(x or 0)`），既膨胀 YAML，也引入 per-row compute 开销。

本变更聚焦一个最小但高频的缺口：**在 ref 字段定义处声明“relation miss 时的默认值”**，由框架在 ref 写回阶段内联处理。

约束：
- 运行时核心需保持 Python 3.6 兼容。
- YAML schema 是生成物（`*.gen.*` 禁止手改），authoring surface 变更必须落到 schema_dsl SSOT 并经生成入口刷新。
- 语义必须避免“miss vs hit-but-null”歧义；v1 只做 relation miss。

## Goals / Non-Goals

**Goals:**
- 在 `main_source.fields.*` / `sources.*.fields.*` 的 ref 字段上支持 `default` ordered cases。
- v1 仅支持 `when: relation_miss`，并实现 `literal` / `call_by` 二选一（oneOf）。
- `literal` fast-path：常量缺省值在执行期无需解释器参与。
- `call_by` 复用既有 callable 引用/allowlist/builtin 解析机制。
- 严格校验：`default` 仅允许出现在带 `relation:` 的字段上；未知 `when` fail-fast。

**Non-Goals:**
- 不实现 `hit_null`/`empty_string` 等“命中但值为空”的缺省规则（后续可通过扩展 `when` 枚举添加）。
- 不实现 `ensure_keys`/维度 roster 补行（另一个正交问题）。
- 不引入新的全局 YAML guardrails/优先级系统（全局策略可由 Python 侧注入，避免 authoring surface 膨胀）。

## Decisions

### Decision 1: 语法采用 `default: [cases...]` first-match

选择 ordered cases 的原因：
- 避免 “default/default_by” 的二字段命名歧义，统一为一个 `default` 节点。
- 为未来扩展其他缺省触发条件预留空间（增加新的 `when` 值，不需要再加新的顶层字段名）。
- first-match 明确、可预测，避免多处声明导致的优先级不透明。

### Decision 2: v1 仅支持 `when: relation_miss`

原因：
- relation miss 属于“联表没命中”的结构性缺失，是 `_safe_*` 的主要根因。
- hit-but-null 的含义依赖 extract/value_cast 细节，容易与业务数据质量混淆；需要独立讨论可观测性与治理边界。

### Decision 3: default 仅允许用于 ref 字段（带 `relation:`）

原因：
- 避免语义扩散：对非 ref 字段，“缺失”的定义不清晰（是字段不存在？extract 失败？值为空？）。
- 运行期注入点清晰：ref miss 的判断天然发生在 `LoadRef` 写回路径。

### Decision 4: `call_by` 必须显式包含 `()`

原因：
- 与现有 `call_by` 设计对齐（字符串表达式 + 运行期绑定），并降低“把引用当常量”的误用概率。
- 为后续 callable preflight 提供更稳定的解析信号（无括号时语义更容易歧义）。

### Decision 5: value_cast 在 default 选值后仍执行

执行顺序（简化）：`(hit/miss 判定) -> (取原值或 default 值) -> value_cast -> 写回`.

原因：
- 保持字段类型语义一致：default 只是补一个“来源值”，类型边界仍由 `value_cast` 统一裁决。
- 允许 `literal` 用 YAML 可表达的标量写法覆盖更宽类型（例如 decimal 字段用 `literal: 0`）。

### Decision 6: `default[*].call_by` MUST 仅依赖 “pre-ref 可用字段”，并在编译期 fail-fast

本变更将 `default[*].call_by` 视为“LoadRef miss 写回路径中的一个小计算”，其求值时机早于其它 ref 字段/派生字段的计算完成。

为避免 “依赖尚未就绪字段 → 隐式变 None → 错误被隐藏且难排查”，系统 MUST 在编译/校验阶段对 `default[*].call_by` 的依赖闭包做静态检查：

- 仅允许引用 **pre-ref 可用** 的字段（main_source 非 ref 字段 + 仅依赖这些字段的 derived 字段）
- 一旦依赖到任何需要 `LoadRef` 才能得到的字段（ref 字段/依赖 ref 的派生字段），MUST fail-fast 并给出可定位诊断

该校验结果同时用于运行期 compile 的最后兜底与 editor/LSP diagnostics（复用同一 validator 语义，确保编辑时就能提示）。

## Risks / Trade-offs

- [风险] default 被误认为能处理 hit-but-null → [缓解] v1 严格限定 `when`，并在 schema/hover 文案明确 “仅 relation miss”。
- [权衡] 增加 `LoadRef` 分支逻辑 → [缓解] literal fast-path + 仅在 miss 分支触发，hit 路径零开销。

## Migration Plan

- 该能力为 additive：未声明 `default` 时行为不变（miss 仍写回 `None`）。
- 下游迁移建议：
  - 将 `_safe_*: int(x or 0)` 迁移为 ref 字段 `default` case（对 relation miss 生效）。
  - 对比率类字段，优先将 per-row compute 后移到 aggregate/post（不在本变更范围内）。

## Open Questions

（v1 无未决问题）
